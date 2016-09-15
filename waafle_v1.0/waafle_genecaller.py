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
from collections import Counter


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
        "-lap", "--overlap-hits",
        default=0.5,
        type=float,
        help="overlap at which to merge hits into groups",
        )
    parser.add_argument(
        "-l", "--length",
        default=0,
        type=float,
        help="length constraint for genes",
        )
    parser.add_argument(
        "-scov", "--scov_hits",
        default=0,
        type=float,
        help="scoverage filter for hits",
        )
    parser.add_argument(
        "-s", "--strand",
        action="store_true",
        help="turn on strand specific gene calling",
        )
    args = parser.parse_args()
    return args

def hits2ints( hitlist, scov ):
    """ For a list of hits, filter by scoverage """
    intervals = []
    for hit in hitlist:
        strand = wu.convert_strand( hit.sstrand )
        if hit.scov_modified >= scov:
                intervals.append( [hit.qstart, hit.qend, strand] )
    return intervals

def overlap_inodes( inode1, inode2 ):
    """ compute overlap between two intervals """
    a1, b1 = inode1.start, inode1.stop
    a2, b2 = inode2.start, inode2.stop
    overlap = wu.calc_overlap( a1, b1, a2, b2 )
    return overlap
    
def merge_inodes( *inodes ):
    """ merge overlapping intervals into a single node """
    start = stop = None
    strand_rank = []
    for inode in inodes:
        if start is None or inode.start < start:
            start = inode.start
        if stop is None or inode.stop > stop:
            stop = inode.stop
        strand_rank.append( [len( inode ), inode.strand] )
    # assign strand of largest interval to the merged interval
    strand = sorted( strand_rank )[-1][1]
    return wu.INode( start, stop, strand )

def make_inodes( intervals ):
    """ convert list of intervals to list of inodes """
    inodes = []
    for interval in intervals:
        start, stop = interval[0:2]
        strand = "+" if len( interval ) < 3 else interval[2]
        inodes.append( wu.INode( start, stop, strand ) )
    return inodes
        
def overlap_intervals( intervals, threshold, strand_specific ):
    """ find and collapse overlapping intervals """
    inodes = make_inodes( intervals )
    inodes = sorted( inodes, key=lambda inode: inode.start )
    for index, inode1 in enumerate( inodes ):
        for inode2 in inodes[index+1:]:
            if inode1.strand == inode2.strand or not strand_specific:
                score = overlap_inodes( inode1, inode2 )
                if score >= threshold:
                    # store as edge in network
                    inode1.attach( inode2 )
                    inode2.attach( inode1 )
                elif score == 0:
                    # no further inode2 can overlap this inode1
                    break
    # divide intervals into "connected components"
    cclist = []
    for inode in inodes:
        if not inode.visited:
            cclist.append( inode.get_connected_component( ) )
    # merge intervals and report as simple lists
    results, numhits = [], []
    for cc in cclist:
        merged = merge_inodes( *cc ).to_list( )
        originals = [inode.to_list( ) for inode in cc]
        results.append( merged )
        numhits.append( len(originals) )
    return results, numhits

# ---------------------------------------------------------------
# main
# ---------------------------------------------------------------

def main():
    """
    This script does the following:
    1) Organizes BLAST hits that pass the scov filter into intervals.
    2) Sort intervals by start site and find connected intervals.
    3) Merge connected intervals into genes, and filter by genelen.
    4) Print genes as gff.
    """
    args = get_args()
    fh =  wu.try_open( args.out, "w" )
    writer = csv.writer( fh, dialect="excel-tab" )

    for contig, hitlist in wu.iter_contig_hits( args.input ):
        intervals = hits2ints( hitlist, args.scov_hits )
        newintervals, newint_num = overlap_intervals( intervals, args.overlap_hits, args.strand)
                
        counter = 1
        for i in range( len( newintervals ) ):
            gene = newintervals[i]
            numhits = newint_num[i]
            start, end, strand = gene[0], gene[1], gene[2]
            genelen = end - start + 1

            if genelen > args.length:
                score = numhits
                name = 'ID=' + contig + '_' + str(counter)
                writer.writerow( [str(x) for x in [
                                                contig, 
                                                'WAAFLE', 
                                                'CDS', 
                                                start, 
                                                end, 
                                                score, 
                                                strand, 
                                                '0', 
                                                name
                                                ]] ) 
                counter += 1

    fh.close()

if __name__ == "__main__":
    main()
