# Welcome to the WAAFLE Demo

## Table of contents

[TOC]

## What is WAAFLE?

Lateral gene transfer (LGT) is an important mechanism for genome diversification in microbial communities, including the human microbiome. While methods exist to identify LGTs from sequenced isolate genomes, identifying LGTs from community metagenomes remains an open problem. To address this, we developed **WAAFLE**: a **W**orkflow to **A**nnotate **A**ssemblies and **F**ind **L**GT **E**vents.

WAAFLE integrates gene sequence homology and taxonomic provenance to identify metagenomic contigs explained by pairs of microbial clades but not by single clades (i.e. putative LGTs). More specifically, for each locus in a contig, WAAFLE identifies the best hit to each species in a pangenome database. WAAFLE then looks for a species whose minimum per-locus score exceeds a lenient homology threshold (k~1~). If one or more species meet this criterion, then the contig is assigned to the species with the best average score. Otherwise, the process is repeated for pairs of species. If all per-locus scores for a pair of species exceed a stringent homology threshold (k~2~), then the contig is considered a putative LGT between those species.

Consider the following pair of examples:

![Fig. 1](https://bitbucket.org/biobakery/waafle/raw/tip/website/webfig1.png "Fig. 1")

Both cases consider contigs with six protein-coding loci (determined from WAAFLE itself or an independent ORF-calling program such as [Prodigal](https://github.com/hyattpd/Prodigal)). In Example 1, genes from species **C** are able to explain all of the loci reasonably well (with scores exceeding k~1~). Hence, WAAFLE will report this contig as a one-species contig explained by species **C**.

In Example 2, no single species can explain all of the loci (the minimum score for each species is below k~1~). However, the pair of species **A** and **B** have strong hits (>k~2~) to all loci, and so WAAFLE concludes that this contig may represent an A+B LGT. Given the `AABBAA` synteny pattern, a B-to-A transfer would appear to be the more likely mechanism.

Note that in Example 2, if species **C** had hits to the 2nd and 5th loci that exceeded k~1~ (as in Example 1), WAAFLE's algorithm would conservatively favor the weaker one-species explanation for the contig rather than invoking a two-species (LGT-based) explanation.

## Getting started with WAAFLE

You can test if WAAFLE is available in your computing environment by running `waafle_search -h`, which should return a help menu. If it doesn't, then please consult the [WAAFLE manual](https://bitbucket.org/biobakery/waafle/src/default/README.md) for help installing and setting up WAAFLE.

If you cloned the WAAFLE repository, or are working in a bioBakery computing environment, you may already have the WAAFLE demo files available to you. If not, or if you're not sure, you can [download them from here](https://bitbucket.org/biobakery/waafle/get/tip.zip).

When the download is complete (a file called `tip.zip`), unpack it by running `unzip tip.zip` on the command line. Then use the `cd` command to enter the resulting folder (called `biobakery-waafle-###`, where `###` is a random string of letters and numbers). You will find a `demo/` as a subfolder of the folder you just entered.

## Demo introduction

Under the WAAFLE `demo/` folder you'll find three subfolders:

* `input/` contains files used in the tutorial.
* `output/` contains the expected outputs from each tutorial step.
* `output_prodigal/` contains the expected outputs from each tutorial step assuming you used [Prodigal](https://github.com/hyattpd/Prodigal) for gene calling rather than WAAFLE itself.

The `input/` folder contains three pieces of data:

* `demo_contigs.fasta` is a set of input contigs derived from [HMP stool sample SRS011084](https://www.hmpdacc.org/hmp/). (These contigs have been pre-screened for uniform coverage to help rule out misassembly events.)
* `demo_waafledb/` is a reduced, WAAFLE-formatted BLAST database.
* `demo_taxonomy.tsv` is a reduced taxonomy file for the species in the BLAST database.

Inspect the demo files with `less` or other shell commands to answer the following discussion questions.

***
* **How many contigs are present in the contigs file?**
* **How many unique species are present in the taxonomy file?** *(Hint: the structure of the taxonomy file is a list of tab-separated child-parent relationships; species entries are prefixed with `s__`.)*
* **Which species has the most supporting genomes in the taxonomy file?** *(Hint: genomes are the leaves of the taxonomy, and are prefixed with `t__`.)*
***

## Step 1. Generate BLAST hits with waafle_search.

The first step in the WAAFLE workflow is to search the input contigs against a WAAFLE-formatted pangenome database. See the options for the `waafle_search` program using the help command:

```
$ waafle_search.py --help
```

The two critical parameters are the query (contigs) and database. Let's search the demo contigs against the demo database:

```
$ waafle_search.py input/demo_contigs.fna input/demo_waafledb/demo_waafledb
```

The command will finish quickly as both the input and database are small. Note the following line from the BLAST command:

```'-outfmt 6 qseqid sseqid qlen slen length qstart qend sstart send pident positive gaps evalue bitscore sstrand'```

This is specifying the format of the tabular BLAST output. WAAFLE uses a number of non-default BLAST alignment statistics to compute its homology scores. You can find descriptions of these statistics in the BLAST detailed help menu, accessible by running `$ blastn -help`.

Let's inspect the BLAST output with `$ less demo_contigs.blastout`:

```
1458  GENE000041992|s__Faecalibacterium_prausnitzii|UniProt=D4JZK5  5194  1347  1347  3675  5021  1347  1     92.72  1249  0   0.0     1947  minus
1458  GENE000042498|s__Faecalibacterium_prausnitzii|UniProt=D4JZK7  5194  1440  1407  830   2236  1     1407  87.21  1227  0   0.0     1602  plus
1458  GENE000041989|s__Faecalibacterium_prausnitzii|UniProt=D4JZK5  5194  1347  1350  3675  5021  1347  1     87.56  1182  6   0.0     1559  minus
1458  GENE000041988|s__Faecalibacterium_prausnitzii|UniProt=D4JZK5  5194  1347  1346  3677  5021  1345  1     87.44  1177  2   0.0     1550  minus
1458  GENE000043174|s__Faecalibacterium_prausnitzii|UniProt=D4JZK6  5194  1281  1283  2349  3626  1281  1     87.45  1122  7   0.0     1478  minus
1458  GENE000042009|s__Faecalibacterium_prausnitzii|UniProt=None    5194  1347  1341  3682  5021  1340  1     86.43  1159  2   0.0     1469  minus
1458  GENE000042343|s__Faecalibacterium_prausnitzii|UniProt=C7H5K2  5194  1434  1377  864   2237  35    1408  82.64  1138  6   0.0     1214  plus
1458  GENE000042322|s__Faecalibacterium_prausnitzii|UniProt=D4K630  5194  1431  1395  850   2237  21    1408  80.72  1126  14  0.0     1074  plus
1458  GENE000042865|s__Faecalibacterium_prausnitzii|UniProt=C7H5K3  5194  1212  654   2415  3065  1206  556   84.56  553   6   0.0     643   minus
1458  GENE000038197|s__Faecalibacterium_prausnitzii|UniProt=D4JZK8  5194  588   575   106   679   1     574   85.57  492   2   4e-170  601   plus
```

The columns of the output match the requested columns from the BLAST command. Most critically, the first and second columns provide a mapping from the input contigs (query sequences) to genes in the demo database (subject sequences). Each subject sequence has the following format:

```UNIQUE-GENE-ID|SPECIES|ANNOTATION=VALUE```

In the demo database, genes have been annotated with UniProt accession numbers. You can look up individual accession numbers on the UniProt website: e.g. [http://www.uniprot.org/uniprot/D4JZK5](http://www.uniprot.org/uniprot/D4JZK5).

Answer the following questions about the BLAST output by using shell commands or visual inspection:

***
* **Which contig received the most BLAST hits?**
* **Did any contigs receive hits to more than one species?**
***

## Step 2. Call genes with waafle_genecaller.

In order to classify the contigs, WAAFLE compares the BLAST hits generated above to a set of predicted protein-coding loci within the contigs, as defined by a [GFF file](https://useast.ensembl.org/info/website/upload/gff.html). WAAFLE includes a utility to call genes within contigs based on the BLAST output itself by clustering the start and stop coordinates of hits along the length of the contig.

```
$ waafle_genecaller.py --help
```

This utility requires a single input to run: the BLAST output file:

```
$ waafle_genecaller.py demo_contigs.blastout
```

This produced a file in GFF format called `demo_contigs.gff`. Inspect its contents using the `less` command:

```
1458  waafle_genecaller  gene  106   679   .  +  0  .
1458  waafle_genecaller  gene  830   2237  .  +  0  .
1458  waafle_genecaller  gene  2349  3626  .  -  0  .
1458  waafle_genecaller  gene  3675  5021  .  -  0  .
1535  waafle_genecaller  gene  975   1992  .  -  0  .
1535  waafle_genecaller  gene  2041  3363  .  -  0  .
1535  waafle_genecaller  gene  3388  4125  .  -  0  .
1535  waafle_genecaller  gene  4486  6028  .  +  0  .
1689  waafle_genecaller  gene  335   1245  .  +  0  .
1689  waafle_genecaller  gene  1798  2779  .  -  0  .
```

Columns 1, 4, and 5 are the most important: they provide an index of the gene start and stop coordinates within each contig.

Answer the following questions about the GFF output by using shell commands or visual inspection:

***
* **Which contig contains the most predicted genes?**
* **Are the contigs 'gene-dense'? Does this match your expectation for prokaryotic genomes?**
***

## Step 3. Find LGT-containing contigs with waafle_orgscorer.

The last step in the WAAFLE workflow is also the most important: comparing per-species BLAST hits with the contig's gene coordinates (loci) to try to find one- and two-species explanations for contigs (as described in the algorithm overview above). This step is peformed by the `waafle_orgscorer` utility. This utility has many tunable parameters, most of which are devoted to filtering and formatting the outputs. 

You can inspect the parameters of `waafle_orgscorer` using the flag `-h` (for a summary) or `--help` (for details):

```
usage: waafle_orgscorer.py [-h] [--outdir <path>] [--basename <str>]
                           [--write-details] [--quiet] [-k1 <0.0-1.0>]
                           [-k2 <0.0-1.0>]
                           [--disambiguate-one <report-best/meld>]
                           [--disambiguate-two <report-best/jump/meld>]
                           [--range <float>] [--jump-taxonomy <1-N>]
                           [--allow-lca] [--ambiguous-fraction <0.0-1.0>]
                           [--clade-genes <1-N>] [--clade-leaves <1-N>]
                           [--sister-penalty <0.0-1.0>]
                           [--weak-loci <ignore/penalize/assign-unknown>]
                           [--transfer-annotations <lenient/strict/very-strict>]
                           [--min-overlap <0.0-1.0>] [--min-gene-length <int>]
                           [--min-scov <float>] [--stranded]
                           contigs blastout gff taxonomy
```

The two most important parameters are k~1~ and k~2~, as introduced in the algorithm summary above.

***
* **What are the default values of k~1~ and k~2~?**
***

Lets try a run of `waafle_orgscorer` with only the four required arguments, `contigs blastout gff taxonomy`:

```
$ waafle_orgscorer.py \
	input/demo_contigs.fna \
	demo_contigs.blastout \
	demo_contigs.gff \
	input/demo_taxonomy.tsv
```

This produces three output files:

* `demo_contigs.lgt.tsv` contains a description of predicted LGT events.
* `demo_contigs.no_lgt.tsv` contains descriptions of contigs explained by single species/clades.
* `demo_contigs.unclassified.tsv` contains descriptions of contigs that could not be explained by either single species or pairs of species.

### Examining one-clade (no-LGT) contigs

Most contigs are assigned to the `no_lgt` bin. Let's inspect a subset of the fields from this file with `cut` and `less`:

```
$ cut -f1,4-7 demo_contigs.no_lgt.tsv | less
```

Which yields:

```
CONTIG_NAME  MIN_SCORE  AVG_SCORE  SYNTENY    CLADE
14237        0.983      0.989      AAAA       s__Faecalibacterium_prausnitzii
14258        0.950      0.994      AAAAAAAAA  s__Eubacterium_rectale
14270        0.992      0.995      AAAA       s__Roseburia_intestinalis
14274        0.833      0.913      AAAA       s__Faecalibacterium_prausnitzii
14307        0.730      0.870      AAAA       s__Faecalibacterium_prausnitzii
14339        0.997      0.999      AAAAAA     s__Roseburia_intestinalis
14449        0.818      0.968      AAAAAA     s__Faecalibacterium_prausnitzii
14496        0.815      0.867      AAAA       s__Faecalibacterium_prausnitzii
14528        0.901      0.917      AAAA       s__Collinsella_aerofaciens
```

In the case of the first contig, 14237, these fields tell us that the contig was best explained by *Faecalibacterium prausnitzii*. The contig had four genes (evident from the `AAAA` synteny). *F. prausnitzii* had a minimum score over these genes of 0.983 (much greater than the threshold of 0.5), and its average score was similarly high at 0.989. We are very confident that this contig represents a fragment of *F. prausnitzii* genome.

Answer the following questions about the one-species contigs by using shell commands, visual inspection, or internet research:

***
* **Are the species detected reasonable for a human gut sample?**
* **Which species contributed the most contigs to the metagenomic assembly?**
* **Which taxonomic assignment was WAAFLE least confident about?**
***

When WAAFLE fails to find a one- or two-species explanation, it repeats its search at the next highest-level clades, looking for (e.g.) one-genus vs. two-genera explanations.

***
* **Are there any instances of this behavior in the `no_lgt` output?**
***

### Examining two-clade (putative LGT) contigs

Now for exciting part: examining the putative LGTs in the `demo_contigs.lgt.tsv` file. We'll again focus on a subset of the output columns:

```
$ cut -f1,4-10 demo_contigs.lgt.tsv
```

Which yields:

```
CONTIG_NAME  MIN_MAX_SCORE  AVG_MAX_SCORE  SYNTENY       DIRECTION  CLADE_A                     CLADE_B                          LCA
12571        0.856          0.965          AABAAAA       B>A        s__Ruminococcus_bromii      s__Faecalibacterium_prausnitzii  f__Ruminococcaceae
```

In the case of the first contig, 12571, these fields tell us that the contig was best explained by a putative LGT between *Ruminococcus bromii* and *Faecalibacterium prausnitzii*: two species that are related at the family level [according to the lowest common ancestor (LCA) field]. The synteny pattern `AABAAAA` suggests that a single *F. prausnitzii* gene (`B`) inserted into the *R. bromii* genome.

The min-max score entry indicates that, across the seven loci of this contig, one of these species always scored at least 0.856 (this exceeded the default k~2~ value of 0.8, allowing the LGT to be called).

Add column 16 to the `cut` command above to inspect the annotations of these genes:

```
ANNOTATIONS:UNIPROT
R5E4K6|D4L7I2|D4JXM0|D4L7I1|D4L7I0|None|D4L7H8
```

By default, WAAFLE assigns the annotation of the best BLAST hit at each locus. Here, the best hit to the sixth `|`-delimitted was not annotated in UniProt (it receives a `None` annotation).

Answer the following questions about the two-species contigs by using shell commands, visual inspection, or internet research:

***
* **What is the function of the LGT'ed gene in the example above?**
* **What is the most remote LGT event (i.e. the event with the highest-level LCA)?**
* **Are there any LGT contigs where the donor and recipient cannot be determined confidently?**
***

Challenge questions:

***
* **Which species is the most frequent LGT donor?**
* **Do any species appear as LGT donors but never as recipients?**
* **How many LGT events occurred per 1,000 assembled genes?**
***

## Extension A: Working with Prodigal gene calls

In the workflow above, we used `waafle_genecaller` to identify potential coding loci in our contigs. As alluded to above, we can also perform this step with an independent open reading frame (ORF) detection system, such as [Prodigal](https://github.com/hyattpd/Prodigal). 

Run prodigal on the input contigs to produce an alternate GFF file:

```
$ ./prodigal.linux \
	-i input/demo_contigs.fna \
	-f gff \
	-o demo_contigs.prodigal.gff
```

(If you don't have Prodigal available on your system, you can use the Prodigal GFF file in `output_prodigal/`.) Inspect the alternate GFF file with `less`. You'll find it has more details than the equivalent file produced by WAAFLE, but the overall format is the same.

Repeat **Step 3** above using the alternate GFF file and adding the argument `--basename demo_contigs.prodigal` to the `waafle_orgscorer` call (this will prevent overwriting the original outputs). Inspect the outputs.

You'll notice that the synteny strings now contain a `~` character. This corresponds to a locus that never received a "good" hit to any species (i.e. with homology score >k~1~). By default, `waafle_orgscorer` will ignore such loci. You can change this behavior with the `--weak-loci` flag.

***
* **How do the results change using the Prodigal GFF file?**
* **What are pros and cons of using an ORF-based gene caller rather than homology-based gene definitions?**
***

## Extension B: Experimenting with LGT-calling parameters

As noted above, there are many options for tuning the behavior of `waafle_orgscorer` using its configuration flags. The default settings for these parameters have all been pre-tuned for high sensitivity and specificity (based on evaluations of synthetic contigs of known LGT status). However, depending on your application, it may be useful to tune parameters for a more sensitive and less specific analysis (or vice versa).

### Raising k~1~

Repeat the original analyis from **Step 3** above, but set k~1~ to 0.8 instead of the default of 0.5 (i.e. so the k~1~ parameter is NOT more lenient than k~2~.)

***
* **What effect does a higher k~1~ have?**
* **Does this make the analysis more or less sensitive/specific?**
***

### Starting with genera

Perform a run adding the parameter `--jump-taxonomy 1`. This will begin the analysis using genus-level clades rather than species-level clades.

***
* **What effect does starting at the genus level have?**
* **Does this make the analysis more or less sensitive/specific?**
***

### Requiring more isolate genome support

Perform a run adding `--clade-leaves 2`. This will require clades in a two-species contig to be supported by at least two isolate genomes.

***
* **What effect does requiring more supporting isolate genomes have on reported LGTs?**
* **What is a potential concern when describing a LGT in which the donor is supported by a single genome?**
***