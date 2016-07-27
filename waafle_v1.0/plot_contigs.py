#!/usr/bin/env/python

from __future__ import print_function
import matplotlib
matplotlib.use('Agg')

import matplotlib.pyplot as plt
import matplotlib.patches as patches
import argparse
import waafle_utils as wu
import numpy as np
from matplotlib.pyplot import cm 
import random
import re

# ---------------------------------------------------------------
# functions
# ---------------------------------------------------------------

def get_args():
    parser = argparse.ArgumentParser(
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
        )
    parser.add_argument(
        "-scores", "--orgscorer",
        required=True,
        help="output from waafle orgscorer"
        )
    parser.add_argument(
        "-results", "--results",
        required=True,
        help="output from waafle aggregator"
        )
    parser.add_argument(
        "-genes", "--genes",
        help="output for genes from Prodigal or WAAFLE in gff format",
        )
    parser.add_argument(
        "-reforgs", "--ref_orgs",
        help="output for reference orgs from NCBI for synthetic contigs only, if available"
        )
    parser.add_argument(
        "-contigs", "--contiglist",
        help="list of contigs to output plots for"
        )
    parser.add_argument(
        "-taxa", "--taxalevel",
        help="taxa level"
        )
    args = parser.parse_args()
    return args

#----------------------------------------------------------------
# constants
#----------------------------------------------------------------
taxalevels = {'k':0, 'p':1, 'c':2, 'o':3, 'f':4, 'g':5, 's':6, 't':7}

#----------------------------------------------------------------
# functions
#----------------------------------------------------------------



# ---------------------------------------------------------------
# main
# ---------------------------------------------------------------

def main():
    args = get_args()

    # Parse orgscorer data
    dict_mytaxa = {}
    for contig, taxalist in wu.iter_contig_taxa( args.orgscorer ):
        dict_mytaxa[contig] = taxalist

    # Parse gff (either Prodigal or WAAFLE)
    if args.genes:
        dict_genes = {}
        for contig, gfflist in wu.iter_contig_genes( args.genes ):
            dict_genes[contig] = gfflist

    """
    # Parse answer data IF provided
    if args.ref_orgs:
        dict_reforgs = {}
        for astrline in open( args.ref_orgs ): 
            aastrline = astrline.strip().split('\t')
            index = taxalevels[args.taxalevel]
            donor = aastrline[3].split('|')[index]
            recip = aastrline[2].split('|')[index]
            dict_reforgs[ aastrline[1] ] = [recip, donor]
    """

    # Parse final results into dict
    dict_results = {}
    for contiginfo in open( args.results ):
        line = contiginfo.strip().split('\t')
        if line[0] == 'contig': #remove header
            continue
        else:
            result = wu.Result( line )
            dict_results[ result.contig ] = result.__dict__[args.taxalevel]

    # Loop through list of contigs
    for astrline in open( args.contiglist ):
        contig = astrline.strip()
        taxalist = dict_mytaxa[contig]
        results = dict_results[contig]
        
        # Arrange waafle genes in data structure
        dict_waaflegenes = {}
        for taxa in taxalist:
            if taxa.strand == '+':
                dict_waaflegenes[taxa.gene] = [taxa.genestart, taxa.geneend, taxa.uniref50, taxa.uniref90]
            else:
                dict_waaflegenes[taxa.gene] = [taxa.geneend, taxa.genestart, taxa.uniref50, taxa.uniref90]

        # Make colors for taxa and arrange taxa in data structure
        orgset = set([])
        coloredorgs = wu.split_info( results )[3]
        bcolors = cm.RdYlBu(np.linspace(0, 1, len( coloredorgs )))
        gcolors = cm.gray( np.linspace(0, 1, 1 ) )
        dict_taxacolor, dict_waafletaxa, counter = {}, {}, 0
        contiglen = 0
        for info in taxalist:
            contiglen = float( info.length )
            abbrtaxa = info.taxa.split('|')[taxalevels[args.taxalevel]]
            if abbrtaxa in coloredorgs and abbrtaxa not in dict_waafletaxa.keys():
                dict_taxacolor[abbrtaxa] = bcolors[counter]
                counter += 1
            elif abbrtaxa not in coloredorgs: 
                dict_taxacolor[abbrtaxa] = gcolors[0] #colors[i]
            if abbrtaxa in dict_waafletaxa.keys():
                scorelist, startlist, endlist = [], [], []
                oldscores, oldstarts, oldends = dict_waafletaxa[ abbrtaxa ]
                if taxa.strand == '+':
                    startlist = info.taxastart.split(',')
                    endlist = info.taxaend.split(',')
                else:
                    startlist = info.taxaend.split(',')
                    endlist = info.taxastart.split(',')
                scorelist = [info.score]*len(startlist)
                dict_waafletaxa[ abbrtaxa ] = [ oldscores + scorelist, oldstarts + startlist, oldends + endlist ]
            else:
                scorelist, startlist, endlist = [], [], []
                if taxa.strand == '+':
                    startlist = info.taxastart.split(',')
                    endlist = info.taxaend.split(',')
                else:
                    startlist = info.taxaend.split(',')
                    endlist = info.taxastart.split(',')
                scorelist = [info.score]*len(startlist)
                dict_waafletaxa[abbrtaxa] = [scorelist, startlist, endlist]
        
        # Initiate the plots      
        taxarows = len( dict_waafletaxa.keys() )
        generows = len( dict_waaflegenes.keys() )
        rows = (taxarows + generows)*5/2 + 4 #make taxa and gene rows 2/5 of the plot, plus 4 for spaces in between plots
        plotrows = rows - taxarows - generows - 4
        fig = plt.figure(figsize=(rows, rows), dpi=300)
        
        # Plot for orgscorer hits
        h_waafle = plt.subplot2grid( (rows,1), (0,0), rowspan=plotrows*2/3, colspan=1 )
        h_waafle.set_ylim( -0.1, 1.1 )
        h_waafle.set_xlim( 0, contiglen )
        h_waafle.set_ylabel( 'scores' )
        h_waafle.get_xaxis().set_ticks( np.arange(0, contiglen, contiglen/10) )

        # Plot for genes
        h_genes = plt.subplot2grid( (rows,1), (1+plotrows*2/3,0), rowspan=plotrows*1/3, colspan=1 )
        h_genes.set_ylim( 0, 1 )
        h_genes.set_xlim( 0, contiglen )
        h_genes.get_xaxis().set_ticks(np.arange( 0, contiglen, contiglen/10) )
        h_genes.get_yaxis().set_ticks([0, 0.5, 1])
        h_genes.set_ylabel( 'genes' )

        # Plot for taxa legend
        h_taxaleg = plt.subplot2grid( (rows,1), (2+plotrows,0),rowspan=taxarows, colspan=1 ) #for taxa annotations

        # Plot for Uniref annotations
        h_geneleg = plt.subplot2grid( (rows,1), (3+plotrows + taxarows, 0), rowspan=generows, colspan=1 ) #for Uniref annotations
        h_geneleg.set_xlim( 0, contiglen )
        h_geneleg.set_ylim( 0, len( dict_waaflegenes.keys() )*2 )

        # Plot taxa and taxa legend
        h_taxaleg.set_xlim( 0, contiglen )
        h_taxaleg.set_ylim( 0, len(dict_taxacolor.keys())*2 )
        xlab = 0
        ylab = len(dict_taxacolor)*2
        ylab -= 1
        for taxa in dict_waafletaxa.keys():
            
            #Plot all taxa
            scores, starts, ends = dict_waafletaxa[taxa]
            diffs = list( np.array( [int(x) for x in ends] ) - np.array( [int(y) for y in starts] ) )
            adjdiffs = []
            for i in range( len( diffs ) ):
                value = diffs[i]
                arrowhead = abs( 0.05 * value )
                if float(value) < 0:
                    newvalue = value + arrowhead
                else:
                    newvalue = value - arrowhead
                h_waafle.arrow( float( starts[i] ), float( scores[i] ), newvalue, 0, width=0.02, color=dict_taxacolor[taxa], head_width=0.02, head_length=arrowhead, alpha=0.4 )
            
            #Plot taxa legend
            p = patches.Rectangle( (xlab, ylab), contiglen/20, 1, color=dict_taxacolor[taxa], alpha=0.4)
            h_taxaleg.add_patch(p)
            h_taxaleg.text( xlab + contiglen/20, ylab + 0.5, str(taxa), fontsize=12 ) #contiglen/200 )
            xlab += contiglen/4
            if xlab >= contiglen:
                xlab = 0
                ylab -= 2
        h_taxaleg.set_axis_off()
       
        # Plot waafle genes
        score = 1
        ylab = len( dict_waaflegenes.keys() )
        for gene in dict_waaflegenes.keys():
            start, end, uniref50, uniref90 = dict_waaflegenes[ gene ]
            if score <= 0:
                score = 1
            else:
                score -= 0.1
            diff = float( end ) - float( start )
            if float(diff) < 0:
                arrowhead = abs( 0.05*diff )
                newdiff = diff + arrowhead
            else:
                newdiff = diff - arrowhead
            h_genes.arrow( dict_waaflegenes[gene][0], score, newdiff, 0, width=0.04, color="blue", head_width=0.04, head_length=arrowhead, alpha=0.9 )
            ylab -= 1
            h_geneleg.text(0, ylab, 'Gene' + str(gene) + ' Uniref50:' + uniref50, fontsize=8 )
            ylab -= 0.5
            h_geneleg.text(0, ylab, 'Gene' + str(gene) + ' Uniref90:' + uniref90, fontsize=8 )
        h_geneleg.set_axis_off()
        """ 
        # Plot reference genes (Prodigal or AnswerKey) and taxa (if AnswerKey) 
        DR = False
        if args.ref_orgs:
            DR = True
    
        if args.ref_genes:
            # Initiate the plot
            h_refgenes = plt.subplot2grid( (rows,2), (3,0), rowspan=1, colspan=2 )
            gfflist = dict_refgenes[contig]
	    score = 1
            for gene in gfflist:
                ID = gene.attribute.split(';')[0]
                if re.search( 'donor', ID ) and DR == True:
			colors = 'red'
		elif not re.search('donor', ID ) and DR == True:
                        colors = 'blue'
                else:
                        colors = 'black'
                
                # Set y-axis
                if score <= 0:
                    score = 1
                else:
                    score -= 0.1		
                if gene.strand == '+':
                    h_refgenes.arrow( gene.start, score, gene.end-gene.start, 0, width=0.04, color=colors, head_width=0.04, head_length=headlen, alpha=0.4 )
                    if re.search('donor', ID ) and DR == True:
                        h_refgenes.text( (gene.start+gene.end)/2, score, 'donor:' + dict_reforgs[contig][1] )
                    elif not re.search('donor', ID ) and DR == True:
                        h_refgenes.text( (gene.start+gene.end)/2, score, 'recip:' + dict_reforgs[contig][0] )
                else:
                    h_refgenes.arrow( gene.end, score, gene.start-gene.end, 0, width=0.04, color=colors, head_width=0.04, head_length=headlen, alpha=0.4)
                    if re.search('donor', ID ) and DR == True:
                        h_refgenes.text( (gene.start+gene.end)/2, score, 'donor:' + dict_reforgs[contig][1] )
                    elif not re.search('donor', ID ) and DR == True:
                        h_refgenes.text( (gene.start+gene.end)/2, score, 'recip:' + dict_reforgs[contig][0] )
            
            h_refgenes.set_ylim( 0, 1 )
            h_refgenes.set_xlim( 0, contiglen )
            h_refgenes.get_yaxis().set_ticks([0, 0.5, 1])
            h_refgenes.set_xlabel( 'coordinates (bp)' )
            h_refgenes.set_ylabel( 'answers' )
        """
        filename = contig + '.pdf'
        plt.savefig( filename )
        plt.close(fig)
        

if __name__ == "__main__":
    main()
