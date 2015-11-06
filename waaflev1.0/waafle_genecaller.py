#!/usr/bin/env python

"""
WAAFLE MODULE: waafle_genecaller.py

Authors:
Tiffany Hsu
Eric Franzosa

This script interprets waafle blast output to make gene calls.
Run with the "-h" flag for usage help.

Details of the GTF/GFF file format:

Fields must be tab-separated. 
Empty columns should be denoted with a '.'.

0: seqname - name of the chromosome or scaffold
1: source - name of the program that generated this feature
2: feature - feature type name, e.g. Gene, Variation, Similarity
3: start - Start position of the feature, with sequence numbering starting at 1.
4: end - End position of the feature, with sequence numbering starting at 1.
5: score - A floating point value.
6: strand - defined as + (forward) or - (reverse).
7: frame - One of '0', '1' or '2'.
8: attribute - A semicolon-separated list of tag-value pairs.
"""

from __future__ import print_function # python 2.7+ required
import os, sys, csv, argparse
import waafle_utils as wu
from operator import itemgetter, attrgetter, methodcaller


# ---------------------------------------------------------------
# functions
# ---------------------------------------------------------------

def get_args():
    """
    Get arguments passed to script
    """
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
        )
    parser.add_argument( 
        "-i", "--input",
        required=True,
        help="output from waafle_search"
        )
    parser.add_argument( 
        "-o", "--out",
        default="waafle-genes.gff",
        help="waafle gene calls",
        )
    parser.add_argument(
        "-l", "--overlap",
        default=0.5,
        type=float,
        help="overlap at which to merge hits into genes",
        )
    args = parser.parse_args()
    return args


def hits2coords( hitlist ):
    """
    For a list of hits, get start/end sites for positive and negative strands (two lists).
    """
    poscoordslist, negcoordslist = [], []
    for hit in hitlist:
	start = hit.qstart
	end = hit.qend
        if hit.sstrand == 'minus':
            negcoordslist.append( [start, end] )
        else:
            poscoordslist.append( [start, end] )
    return poscoordslist, negcoordslist


def coords2groups( coordslist, overlap_thresh ):
    """
    Bin a list of hits into groups by start/end coordinates.
    """
    groups = []
    for start, end in coordslist:
        group_add = False 
        if len( groups )== 0:
            groups.append( [start, end] )
	    continue
        else:
            for i in range( len( groups ) ):
                overlap = wu.calc_overlap( groups[i][0], groups[i][1], start, end )
                if overlap >= overlap_thresh:
                   coord_sorted = sorted( [groups[i][0], groups[i][1], start, end] )
                   groups[i] = [coord_sorted[0], coord_sorted[3]]
                   group_add = True
                    
                if i == len( groups ) - 1 and group_add == False:
                   groups.append( [start, end] )
    return groups


def groups2genes( groups, overlap_thresh ):
    """
    Bin a list of groups into genes by start/end coordinates (of groups).
    """
    genes = []
    #Sort groups by end and start coordinates
    groups.sort( key=itemgetter( 1 ), reverse=True )
    groups.sort( key=itemgetter( 0 ) )
    if len(groups) == 1:
        genes = groups
    else:
        genes = coords2groups( groups, overlap_thresh )
    return genes


def countgenes( genelist, coordlist, sign ):
    """
    Count how many hits are associated with each gene.
    Return the gene coordinates (start and end), strand, and count as a list. 
    """
    for i in range( len( genelist ) ):
        genelist[i].append(sign)
        counter = 0
        for startcoord, endcoord in coordlist:
            if startcoord >= genelist[i][0] and endcoord <= genelist[i][1]:
                counter += 1
        genelist[i].append(float(counter))
    return genelist


def printgff( gffrow ):
    """
    Format the gff class into a ordered list for printing.
    """
    gfflist = [ gffrow.seqname,
                gffrow.source,
                gffrow.feature,
                gffrow.start,
                gffrow.end,
                gffrow.score,
                gffrow.strand,
                gffrow.frame,
                gffrow.attribute
                ]
    return gfflist


def writegff( contig, posgenelist, neggenelist ):
    """
    For each contig, sort all genes by start coordinate regardless of strand.
    Output each gene in gff format to a new file.
    """
    allgenelist = posgenelist + neggenelist
    allgenelist.sort( key=itemgetter( 0 ) )
    counter = 1

    gfflist = []
    for gene in allgenelist: 
        gffrow = wu.GFF( [] )
        gffrow.seqname = contig
        gffrow.source = 'WAAFLE'
        gffrow.feature = 'CDS'
        gffrow.start = gene[0]
        gffrow.end = gene[1]
        gffrow.score = gene[3]
        gffrow.strand = gene[2]
        gffrow.frame = '0'
        gffrow.attribute = 'ID=' + contig + '_' + str(counter)
        #gffrow.genenum( gffrow.attribute )
        counter += 1
        gffline = printgff( gffrow )
        gfflist.append( gffline )
    return gfflist
        

# ---------------------------------------------------------------
# main
# ---------------------------------------------------------------

def main():
    args = get_args()
    with wu.try_open( args.out, "w" ) as fh:
            writer = csv.writer( fh, dialect="excel-tab" )

            for contig, hitlist in wu.iter_contig_hits( args.input ):
                hitlist_sorted = sorted( hitlist, key=attrgetter( 'length', 'bitscore' ), reverse=True )
                poscoordlist, negcoordlist = hits2coords( hitlist_sorted )
                posgrouplist = coords2groups( poscoordlist, args.overlap )
                neggrouplist = coords2groups( negcoordlist, args.overlap )
                posgenelist = groups2genes( posgrouplist, args.overlap )
                neggenelist = groups2genes( neggrouplist, args.overlap )
                posgenecount = countgenes( posgenelist, poscoordlist, '+' )
                neggenecount = countgenes( neggenelist, negcoordlist, '-' )
                gfflist = writegff( contig, posgenecount, neggenecount )
                for gff in gfflist:
                    writer.writerow( gff )
    
    fh.close()

if __name__ == "__main__":
    main()
