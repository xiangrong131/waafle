#!/usr/bin/env python

"""
This module is a part of:
WAAFLE, the [W]orkflow to [A]nnotate [A]ssemblies and [F]ind [L]GT [E]vents

Copyright (c) 2018 Harvard T.H. Chan School of Public Health

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
"""

from __future__ import print_function # Python 2.7+ required

import os
import sys
import re
import argparse
from collections import Counter

import numpy as np

from waafle_packaging import utils as wu
from waafle_packaging.waafle_genecaller import attach_shared_args

# ---------------------------------------------------------------
# description
# ---------------------------------------------------------------

description = wu.describe( """
{}: Step 2 in the WAAFLE pipeline

Merges blast hits into genes on contigs-of-interest. Uses corresponding
taxonomy file, and the WAAFLE algorithm, to identify contigs that are
best explained by a single clade vs. a pair of clades. The latter events
correpond to putative LGTs.
""".format( sys.argv[0] ) )

# ---------------------------------------------------------------
# constants
# ---------------------------------------------------------------

c_update = 100
c_precision = 3
c_annotation_prefix = "ANNOTATIONS:"
c_missing_annotation = "N/A"
c_empty_field = "-"
c_delim0 = "; "
c_delim1 = "|"
c_delim2 = ":"

# note: "A" and "B" hardcoded
c_synchar_ambiguous = "*"
c_synchar_ignored = "~"
c_synchar_error = "!"

c_formats = {}

c_formats["lgt"] = """
contig_name
call
contig_length
min_max_score
avg_max_score
synteny
direction
clade_A
clade_B
lca
melded_A
melded_B
taxonomy_A
taxonomy_B
loci
"""

c_formats["no_lgt"] = """
contig_name
call
contig_length
min_score
avg_score
synteny
clade
melded
taxonomy
loci
"""

c_formats["unclassified"] = """
contig_name
call
contig_length
loci
"""

for name, items in c_formats.items( ):
    c_formats[name] = [k for k in items.split( "\n" ) if k != ""]

# ---------------------------------------------------------------
# cli
# ---------------------------------------------------------------

def get_args( ):

    parser = argparse.ArgumentParser(
        description=description, 
        formatter_class=argparse.RawTextHelpFormatter,
        )

    # input params
    g = parser.add_argument_group( "required inputs" )
    g.add_argument(
        "contigs",
        help="contigs file (.fasta format)",
        )
    g.add_argument(
        "blastout",
        help="output of waafle_search for one set of contigs (.blastout)",
        )
    g.add_argument(
        "gff",
        help="gene calls (from waafle_genecaller or user-supplied) for <contigs> (.gff)",
        )
    g.add_argument(
        "taxonomy",
        help="taxonomy file for the blast database used to make <blastout>",
        )

    # output params
    g = parser.add_argument_group( "output formatting" )
    g.add_argument(
        "--outdir",
        default=".",
        metavar="<path>",
        help="directory for writing output files\n[default: .]",
        )
    g.add_argument(
        "--basename",
        default=None,
        metavar="<str>",
        help="basename for output files\n[default: derived from input]",
        )

    # main waafle params
    g = parser.add_argument_group( "main parameters" )
    g.add_argument(
        "-k1", "--one-clade-threshold",
        type=float,
        default=0.5,
        metavar="<0.0-1.0>",
        help="minimum per-gene score for explaining a contig with a single clade\n[default: 0.5]",
        )
    g.add_argument(
        "-k2", "--two-clade-threshold",
        type=float,
        default=0.8,
        metavar="<0.0-1.0>",
        help="minimum per-gene score for explaining a contig with a pair of clades (putative LGT)\n[default: 0.8]",
        )
    g.add_argument(
        "--disambiguate-one",
        choices=["report-best", "meld"],
        default="meld",
        metavar="<report-best/meld>",
        help="what to do when other one-clade explanations fall within <--range> of the best explanation\n[default: meld]",
        )
    g.add_argument(
        "--disambiguate-two",
        choices=["report-best", "jump", "meld"],
        default="meld",
        metavar="<report-best/jump/meld>",
        help="what to do when other two-clade explanations fall within <--range> of the best explanation\n[default: meld]",
        )
    g.add_argument(
        "--range",
        type=float,
        default=0.05,
        metavar="<float>",
        help="when disambiguating, consider explanations within <--range> of the best explanation\n[default: 0.05]",
        )
    g.add_argument(
        "--jump-taxonomy",
        type=int,
        default=None,
        metavar="<1-N>",
        help="before starting, perform 1+ 'jumps' up the taxonomy (e.g. species->genus)\n[default: off]",
        )

    # filters
    g = parser.add_argument_group( "post-detection LGT filters" )
    g.add_argument(
        "--allow-lca",
        action="store_true",
        help="when melding LGT clades, allow the LGT LCA to occur as a melded clade\n[default: off]",
        )
    g.add_argument(
        "--ambiguous-fraction",
        type=float,
        default=0.1,
        metavar="<0.0-1.0>",
        help="allowed fraction of ambiguous (A OR B) gene length in a putative A+B contig\n[default: 0.1]",
        )
    g.add_argument(
        "--clade-genes",
        type=int,
        default=None,
        metavar="<1-N>",
        help="required minimum genes assigned to each LGT clade\n[default: off]",
        )
    g.add_argument(
        "--clade-leaves",
        type=int,
        default=None,
        metavar="<1-N>",
        help="required minimum leaf count supporting each LGT clade\n[default: off]",
        )
    g.add_argument(
        "--sister-penalty",
        type=float,
        default=None,
        metavar="<0.0-1.0>",
        help="allowed prevalence of missing genes in sisters of LGT clades\n[default: off]",
        )

    # params related to hit-gene merger
    g = parser.add_argument_group( "gene-hit merge parameters" )
    g.add_argument(
        "--weak-loci",
        choices=["ignore", "penalize", "assign-unknown"],
        metavar="<ignore/penalize/assign-unknown>",
        default="ignore",
        help="method for handling loci that are never assigned to known clades\n[default: ignore]",
        )
    g.add_argument(
        "--transfer-annotations",
        choices=["lenient", "strict", "very-strict"],
        metavar="<lenient/strict/very-strict>",
        default="strict",
        help="stringency of gene annotation transfer to loci\n[default: strict]",
        )
    g.add_argument(
        "--min-overlap",
        type=float,
        default=0.1,
        metavar="<0.0-1.0>",
        help="only merge hits into genes if the longer of the two covers this portion of the shorter\n[default: 0.1]",
        )

    # ****some gene-level params imported from waafle_genecaller for consistency****
    attach_shared_args( g )

    # wrap-up
    args = parser.parse_args( )
    return args

# ---------------------------------------------------------------
# object to store contig-specific data
# ---------------------------------------------------------------

class Contig( ):
    
    def __init__( self, name, args ):

        # name of the contig
        self.name = name
        # program arguments
        self.args = args
        # length of the contig
        self.length = None
        # sequential locus object for each gene on contig
        self.loci = []
        # may be defined later as an array of loci to NOT ignore
        self.mask = None
        # map: locus name -> object
        self.locus_map = {}
        # map: clade -> locus -> np array of per-site scores
        self.site_scores = {}
        # map: clade -> np array of per-gene scores
        self.gene_scores = {}
        # set of clades _currently_ represented on the contig
        self.clades = set( )
        # best one-clade explanation for the contig (Option object)
        self.best_one = None
        # best two-clade explanation for the contig (Option object)
        self.best_two = None
        # homology thresholds (handle corner case of k1>k2)
        self.min_threshold = min( args.one_clade_threshold, args.two_clade_threshold )
        self.max_threshold = max( args.one_clade_threshold, args.two_clade_threshold )
        # threshold for annotation transfer
        if args.transfer_annotations == "lenient":
            self.transfer_threshold = 0.0
        elif args.transfer_annotations == "strict":
            self.transfer_threshold = self.min_threshold
        elif args.transfer_annotations == "very-strict":
            self.transfer_threshold = self.max_threshold

    def attach_loci( self, loci ):
        """ Filter and load genes from GFF into this contig """
        for L in loci:
            if len( L ) >= self.args.min_gene_length:
                self.loci.append( L )
        loci = sorted( loci, key=lambda L: L.start )
        for i, L in enumerate( loci ):
            # assign a name to the locus for convenience
            L.name = str( i + 1 )
            self.locus_map[L.name] = L

    def attach_hits( self, hits ):
        """ Figure out which BLAST hits correspond to which loci """
        for H in hits:
            if H.scov_modified >= self.args.min_scov:
                for i, L in enumerate( self.loci ):
                    # note: <s>strand in Hit specifically
                    if self.args.stranded and H.sstrand != L.strand:
                        continue
                    if hit_locus_overlap( H, L ) >= self.args.min_overlap:
                        self.score_hit( H, L )
        self.clades = set( self.site_scores.keys( ) )
                    
    def score_hit( self, hit, locus ):
        """ Assign site-level scores for hit to appropriate locus """
        l1, l2 = sorted( [locus.start, locus.end] )
        h1, h2 = sorted( [hit.qstart, hit.qend] )
        # get hit into this gene's coordinate system
        h1 = max( 0, h1 - l1 )
        h2 = min( len( locus ) - 1, h2 - l1 )
        # update gene with this hit's score
        ldict = self.site_scores.setdefault( hit.taxon, {} )
        if locus.name not in ldict:
            ldict[locus.name] = np.zeros( len( locus ) )
        ldict[locus.name][h1:h2+1] = np.maximum( ldict[locus.name][h1:h2+1], hit.waafle_score )
        # (potentially) update locus with this hit's annotations
        for system, value in hit.annotations.items( ):
            ref = locus.annotation_scores.get( system, self.transfer_threshold )
            if ref is None:
                # annotation from GFF, don't overwrite
                continue
            elif hit.waafle_score > ref:
                # add/replace
                locus.annotations[system] = value
                locus.annotation_scores[system] = hit.waafle_score

    def update_gene_scores( self ):
        """ Convert nucleotide-level clade scores to gene scores, handle bad loci """
        # clear existing scores (if any)
        self.gene_scores = {}
        # collapse site scores to genes by averaging
        for clade, ldict in self.site_scores.items( ):
            scores = []
            for locus in self.loci:
                if locus.name in ldict:
                    scores.append( np.mean( ldict[locus.name] ) )
                else:
                    scores.append( 0 )
            self.gene_scores[clade] = np.array( scores )
        # compute max per-gene scores (used below)
        maxes = np.zeros( len( self.loci ) )
        for clade, values in self.gene_scores.items( ):
            if clade != wu.c_unknown:
                maxes = np.maximum( maxes, values )
        # weak loci option 1: do nothing
        if self.args.weak_loci == "penalize":
            pass
        # weak loci option 2: spike unknown taxon
        elif self.args.weak_loci == "assign-unknown":
            self.gene_scores[wu.c_unknown] = 1 - maxes
            self.clades.add( wu.c_unknown )
        # weak loci option 3: mask
        elif self.args.weak_loci == "ignore":
            ok_list = []
            for index, value in enumerate( maxes ):
                self.loci[index].ignore = True
                if value >= self.min_threshold:
                    ok_list.append( index )
                    self.loci[index].ignore = False
            self.mask = None if len( ok_list ) == len( self.loci ) else np.array( ok_list )
        # update contig clades (will include "Unknown" if added above)
        self.clades = {clade for clade in self.gene_scores}

    def raise_taxonomy( self, taxonomy ):
        """ Recombines hits according to clade parents, then converts to new gene scores """
        new_site_scores = {}
        for clade, ldict in self.site_scores.items( ):
            parent = taxonomy.get_parent( clade )
            if parent is None:
                continue
            inner = new_site_scores.setdefault( parent, {} )
            for name in ldict:
                if name not in inner:
                    inner[name] = np.zeros( len( self.locus_map[name] ) )
                inner[name] = np.maximum( inner[name], ldict[name] )
        self.site_scores = new_site_scores
        # use the new site scores to update gene scores
        self.update_gene_scores( )

    def score( self, clade1, clade2=None ):
        """ Score one or two clades over the contig """
        # crit is the MIN max score at each locus over the clade(s)
        crit = None
        # rank is the AVG max score at each locus over the clade(s)
        rank = None
        maxes = scores1 = self.gene_scores[clade1]
        if clade2 is not None:
            scores2 = self.gene_scores[clade2]
            maxes = np.maximum( scores1, scores2 )
        # ignore masked positions, if applicable
        maxes = maxes if self.mask is None else maxes[self.mask]
        crit = np.min( maxes )
        rank = np.mean( maxes )
        return crit, rank

# ---------------------------------------------------------------
# contig explanation object
# ---------------------------------------------------------------
            
class Option( ):

    def __init__( self, contig ):
        # link to the associated contig
        self.contig    = contig
        # False if a contig has failed 1+ LGT filters
        self.ok        = True
        # the one- or two-clade critical value
        self.crit      = None
        # the one- or two-clade rank
        self.rank      = None
        # 1st clade (A)
        self.clade1    = None
        # 2nd clade (B)
        self.clade2    = None
        # synteny pattern (e.g. AABBA)
        self.synteny   = None
        # direction of transfer, if known ("B>A")
        self.direction = "A?B"
        # donor if known (B in ^A+B+A+$)
        self.donor     = None
        # recip if known (A in ^A+B+A+$)
        self.recip     = None
        # clade1 tails after melding (e.g. species melded into genus)
        self.tails1    = []
        # clade2 tails after melding
        self.tails2    = []

    def set_synteny_one( self, k1 ):
        scores = self.contig.gene_scores[self.clade1]
        synteny = ""
        for s, L in zip( scores, self.contig.loci ):
            if L.ignore:
                synteny += c_synchar_ignored
            elif s >= k1:
                synteny += "A"
            else:
                synteny += c_synchar_error
        self.synteny = synteny

    def set_synteny_two( self, k2 ):
        scores1 = self.contig.gene_scores[self.clade1]
        scores2 = self.contig.gene_scores[self.clade2]
        synteny = ""
        for s1, s2, L in zip( scores1, scores2, self.contig.loci ):
            if L.ignore:
                synteny += c_synchar_ignored
            elif min( s1, s2 ) >= k2:
                synteny += c_synchar_ambiguous
            elif s1 >= k2:
                synteny += "A"
            elif s2 >= k2:
                synteny += "B"
            else:
                synteny += c_synchar_error
        self.synteny = synteny
        # force "A" to be the clade at the first locus of clear taxonomy
        if re.search( "^[^A]*B", self.synteny ):
            self.clade1, self.clade2 = self.clade2, self.clade1
            switch = {"A":"B", "B":"A"}
            self.synteny = "".join( [switch.get( char, char ) for char in self.synteny] )
        # direction clear? (don't penalize 'ignored' genes)
        if re.search( "^A+B+A+$", self.synteny.replace( c_synchar_ignored, "" ) ):
            self.direction = "B>A"
            self.donor = self.clade1
            self.recip = self.clade2

# ---------------------------------------------------------------
# helper functions
# ---------------------------------------------------------------

def is_ok( option ):
    """ treat None option as not OK """
    return (option is not None and option.ok)

def not_ok( option ):
    """ treat None option as not OK """
    return (option is None or not option.ok)

def hit_locus_overlap( hit, locus ):
    # query = contig; same coordinate space as locus
    a1, a2 = hit.qstart, hit.qend
    b1, b2 = locus.start, locus.end
    # calc_overlap sorts start/end internally
    return wu.calc_overlap( a1, a2, b1, b2 )

def evaluate_contig( contig, taxonomy, args ):
    best_one = explain_one( contig, taxonomy, args )
    best_two = explain_two( contig, taxonomy, args ) if not_ok( best_one ) else None
    escape = 0
    while len( contig.clades ) > 0 and \
            "r__Root" not in contig.clades and \
            not_ok( best_one ) and \
            not_ok( best_two ):
        contig.raise_taxonomy( taxonomy )
        best_one = explain_one( contig, taxonomy, args )
        best_two = explain_two( contig, taxonomy, args ) if not_ok( best_one ) else None
        escape += 1
        if escape > 100:
            wu.die( "  Warning: Runaway taxonomic recursion for", contig.name )
    contig.best_one = best_one
    contig.best_two = best_two

def explain_one( contig, taxonomy, args ):
    options = []
    for clade in contig.clades:
        crit, rank = contig.score( clade )
        if crit >= args.one_clade_threshold:
            option = Option( contig )
            option.crit    = crit
            option.rank    = rank
            option.clade1  = clade
            option.set_synteny_one( args.one_clade_threshold )
            options.append( option )
    best = meld_one( options, taxonomy, args ) if len( options ) > 0 else None
    return best

def explain_two( contig, taxonomy, args ):
    options = []
    potential_clades = []
    # speedup: skip clades that never exceed k2 threshold
    for clade in contig.clades:
        if max( contig.gene_scores[clade] ) >= args.two_clade_threshold:
            potential_clades.append( clade )
    for clade1 in potential_clades:
        for clade2 in potential_clades:
            if clade1 < clade2:
                crit, rank = contig.score( clade1, clade2 )
                if crit >= args.two_clade_threshold:
                    option = Option( contig )
                    option.rank    = rank
                    option.crit    = crit
                    option.clade1  = clade1
                    option.clade2  = clade2
                    option.set_synteny_two( args.two_clade_threshold )
                    options.append( option )
    best = meld_two( options, taxonomy, args ) if len( options ) > 0 else None
    return best

def meld_one( options, taxonomy, args ):
    # note: unlike LGTs, "melds" never invalidate a one-bug explanation
    options = sorted( options, key=lambda x: x.rank )
    best = options[-1]
    options = [k for k in options if best.rank - k.rank <= args.range]
    # meld other options into best?
    if args.disambiguate_one == "meld":
        to_meld = [k.clade1 for k in options]
        best.clade1 = taxonomy.get_lca( *to_meld )
        best.tails1 = taxonomy.get_tails( to_meld, best.clade1 )
    return best

def meld_two( options, taxonomy, args ):
    options = sorted( options, key=lambda o: o.rank )
    best = options[-1]
    options = [k for k in options if best.rank - k.rank <= args.range]
    # apply lgt filters to options individually
    for o in options:
        apply_lgt_checks( o, taxonomy, args )
    # if only one option, no disambiguation needed
    if len( options ) == 1:
        best = best
    # multiple options + best: keep best
    elif args.disambiguate_two == "report-best":
        best = best
    # multiple options + jump: kill best
    elif args.disambiguate_two == "jump":
        best = None
    # multiple options + meld, but inconsistent options: kill best
    elif args.disambiguate_two == "meld" and not meld_precheck( options ):
        best = None
    # multiple options + meld: merge options into best
    elif args.disambiguate_two == "meld":
        clades1 = [o.clade1 for o in options]
        clades2 = [o.clade2 for o in options]
        best.clade1 = lca1 = taxonomy.get_lca( *clades1 )
        best.clade2 = lca2 = taxonomy.get_lca( *clades2 )
        best.tails1 = taxonomy.get_tails( clades1, lca1 )
        best.tails2 = taxonomy.get_tails( clades2, lca2 )
        # post-meld lca check
        if not args.allow_lca:
            new_clades = [best.clade1, best.clade2]
            new_lca = taxonomy.get_lca( *new_clades )
            if new_lca in new_clades:
                best = None
    # should never happen...
    else:
        wu.die( "Unexpected two-clade resolution." )
    return best

def meld_precheck( options ):
    ret = True
    for o in options:
        if not_ok( o ) or o.synteny != options[0].synteny:
            ret = False
    return ret

def apply_lgt_checks( option, taxonomy, args ):
    if args.ambiguous_fraction is not None:
        check_ambiguous_fraction( option, args )
    if args.clade_genes is not None:
        check_clade_genes( option, args )
    if args.clade_leaves is not None:
        check_clade_leaves( option, taxonomy, args )
    if args.sister_penalty is not None:
        check_sister_penalty( option, taxonomy, args )

# ---------------------------------------------------------------
# LGT filtering functions
# ---------------------------------------------------------------

def check_ambiguous_fraction( option, args ):
    total_len = 0
    ambiguous_len = 0
    for char, locus in zip( option.synteny, option.contig.loci ): 
        if char in ["A", "B", c_synchar_ambiguous]:
            total_len += len( locus )
            ambiguous_len += len( locus ) if char == c_synchar_ambiguous else 0
    test = ambiguous_len / float( total_len )
    if test > args.ambiguous_fraction:
        option.ok = False

def check_clade_genes( option, args ):
    clade_genes = Counter( option.synteny )
    test = min( [clade_genes.get( char, 0 ) for char in "AB"] )
    if test < args.clade_genes:
        option.ok = False

def check_clade_leaves( option, taxonomy, args ):
    test = min( [taxonomy.get_leaf_count( clade ) for clade in [option.clade1, option.clade2]] )
    if test < args.clade_leaves:
        option.ok = False

def check_sister_penalty( option, taxonomy, args ):
    C = option.contig
    clade1, clade2 = option.clade1, option.clade2
    sisters, penalties = {}, {}
    # note the unintuitive swap: a B locus is penalized by A's sisters
    sisters["B"] = taxonomy.get_sisters( clade1 ) - {clade2}
    sisters["A"] = taxonomy.get_sisters( clade2 ) - {clade1}
    for i, char in enumerate( option.synteny ):
        if char not in sisters:
            continue
        hits = 0
        for clade in sisters[char]:
            if clade in C.gene_scores:
                # this could arguably be min or max
                if C.gene_scores[clade][i] >= C.min_threshold:
                    hits += 1
        if len( sisters[char] ) > 0:
            hits /= float( len( sisters[char] ) )
        penalties.setdefault( char, [] ).append( hits )
    penalties = {char:np.mean( values ) for char, values in penalties.items( )}
    test = max( penalties.values( ) )
    if test > args.sister_penalty:
        option.ok = False

# ---------------------------------------------------------------
# output formatting
# ---------------------------------------------------------------

def write_result( rowdict, format, handle ):
    if set( rowdict ) != set( format ):
        wu.die( "Format mismatch." )
    else:
        items = []
        for f in format:
            if type( rowdict[f] ) in [float, np.float32, np.float64]:
                rowdict[f] = round( rowdict[f], c_precision )
            items.append( str( rowdict[f] ) if rowdict[f] != "" else c_empty_field )
        try:
            print( "\t".join( items ), file=handle )
        except:
            wu.say( items )
            sys.exit( )

def loci_string( loci ):
    items = []
    for L in loci:
        triple = [L.start, L.end, L.strand]
        triple = [str( k ) for k in triple]
        items.append( c_delim2.join( triple ) )
    return c_delim1.join( items )

def add_functions( rowdict, contig, systems ):
    for s in systems:
        items = []
        for locus in contig.loci:
            items.append( locus.annotations.get( s, c_missing_annotation ) )
        # note: key here must match definition in headers
        rowdict[c_annotation_prefix + s] = c_delim1.join( items )

def format_tails( tails ):
    ret = ""
    if tails is not None:
        items = set( )
        for t in tails:
            if len( t ) > 0:
                items.add( c_delim1.join( t ) )
        ret = c_delim0.join( sorted( items ) )
    return ret

def write_output_files( contigs, taxonomy, args ):

    # open output file handles
    wu.say( "Initializing outputs." )
    if args.basename is None:
        args.basename = os.path.split( args.blastout )[1].split( "." )[0]
    handles = {}
    for option in ["lgt", "no_lgt", "unclassified"]:
        file_name = ".".join( [args.basename, option, "tsv"] )
        handles[option] = open( os.path.join( args.outdir, file_name ), "w" )

    # determine possible function annotation systems
    systems = set( )
    for contig in contigs.values( ):
        for locus in contig.loci:
            for system in locus.annotations:
                systems.add( system )
    for option in c_formats:
        for s in sorted( systems ):
            c_formats[option].append( c_annotation_prefix + s )

    # print headers
    for name in handles:
        print( "\t".join( [k.upper( ) for k in c_formats[name]] ), file=handles[name] )  
        
    # write results (sorted loop over contigs)
    for contig_name in sorted( contigs ):
        contig = contigs[contig_name]
        best_one = contig.best_one
        best_two = contig.best_two
        # unclassified
        if not_ok( best_one ) and not_ok( best_two ):
            rowdict = {
                "contig_name":   contig_name,
                "call":          "unclassified",
                "contig_length": contig.length,
                "loci":          loci_string( contig.loci ),
                }
            add_functions( rowdict, contig, systems )
            write_result( rowdict, c_formats["unclassified"], handles["unclassified"] )
        # no_lgt
        elif is_ok( best_one ):
            clade = best_one.clade1
            rowdict = {
                "contig_name":   contig_name,
                "call":          "no_lgt",
                "contig_length": contig.length,
                "min_score":     best_one.crit,
                "avg_score":     best_one.rank,
                "synteny":       best_one.synteny,
                "clade":         clade,
                "taxonomy":      c_delim1.join( taxonomy.get_lineage( clade ) ),
                "melded":        format_tails( best_one.tails1 ),
                "loci":          loci_string( contig.loci ),
                }
            add_functions( rowdict, contig, systems )
            write_result( rowdict, c_formats["no_lgt"], handles["no_lgt"] )
        # lgt
        elif is_ok( best_two ):
            clade1, clade2 = best_two.clade1, best_two.clade2
            rowdict = {
                "contig_name":   contig_name,
                "call":         "lgt",
                "contig_length": contig.length,
                "min_max_score": best_two.crit,
                "avg_max_score": best_two.rank,
                "synteny":       best_two.synteny,
                "direction":     best_two.direction,
                "clade_A":       clade1, 
                "clade_B":       clade2,
                "lca":           taxonomy.get_lca( clade1, clade2 ),
                "taxonomy_A":    c_delim1.join( taxonomy.get_lineage( clade1 ) ),
                "taxonomy_B":    c_delim1.join( taxonomy.get_lineage( clade2 ) ),
                "melded_A":      format_tails( best_two.tails1 ),
                "melded_B":      format_tails( best_two.tails2 ),
                "loci":          loci_string( contig.loci ),
                }
            add_functions( rowdict, contig, systems )
            write_result( rowdict, c_formats["lgt"], handles["lgt"] )

    # wrap up
    for h in handles.values( ):
        h.close( )

# ---------------------------------------------------------------
# main
# ---------------------------------------------------------------

def main( ):

    args = get_args( )
    wu.say( "Loading taxonomy." )
    taxonomy = wu.Taxonomy( args.taxonomy )

    # initialize contigs
    wu.say( "Initializing contigs." )
    contigs = {}
    contig_lengths = wu.read_contig_lengths( args.contigs )
    for contig_name, length in contig_lengths.items( ):
        C = Contig( contig_name, args )
        C.length = length
        contigs[contig_name] = C

    # process gff
    wu.say( "Adding gene coordinates." )
    for contig_name, loci in wu.iter_contig_loci( args.gff, attach_annotations=False ):
        if contig_name not in contigs:
            wu.say( "  Unknown contig in <gff> file", contig_name )
            continue
        C = contigs[contig_name]
        C.attach_loci( loci )

    # parse hits, process contigs
    wu.say( "Analyzing contigs." )
    if len( contigs ) > c_update:
        wu.say( "  Progress =" )
    progress = 0

    # major contig loop
    for contig_name, hits in wu.iter_contig_hits( args.blastout ):
        if contig_name not in contigs:
            wu.say( "  Unknown contig in <blastout> file", contig_name )
            continue
        # this is a good contig
        progress += 1
        if progress % c_update == 0:
            wu.say( "  {:.1f}%".format( 100 * progress / float( len( contigs ) ) ) )
        # attach hits to genes
        C = contigs[contig_name]
        C.attach_hits( hits )
        C.update_gene_scores( )
        # initial jumps?
        if args.jump_taxonomy is not None:
            for j in range( args.jump_taxonomy ):
                C.raise_taxonomy( taxonomy )
        # evaluate; note: the 'ignore' option can result in "empty" contigs
        if not all( [L.ignore for L in C.loci] ):
            evaluate_contig( C, taxonomy, args )

    # wrap up
    write_output_files( contigs, taxonomy, args )
    wu.say( "Finished successfully." )
                    
if __name__ == "__main__":
    main( )