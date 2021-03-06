# -*- coding: utf-8 -*-
import ConfigParser
import datetime
import optparse
import tempfile
import sys
import os
import traceback
import shutil
import multiprocessing as mp
import utilsSR.utilsSR as utils
import subprocess
from inspect import currentframe, getframeinfo
from operator import itemgetter

def identOnCov(COV):
	"""
		Calculate start and end of a zone with coverage information

		:param COV: The coverage file
		:type COV: str
		:return: A list containing chromosome, start and end
		:rtype: list
	"""
	chr = ""
	file = open(COV)
	liste_cov = []

	for line in file:
		if line.strip():
			data = line.split()
			liste_cov.append(int(data[2]))
			if chr == "":
				chr = data[0]
				min = data[1]
				max = data[1]
			elif chr == data[0]:
				max = data[1]
			else:
				raise ValueError('There is a bug in recalc_border : several chromosomes are found in the cov file')
	return [chr, min, max]


def extract_function_name():
	"""Extracts failing function name from Traceback

	by Alex Martelli
	http://stackoverflow.com/questions/2380073/\
	how-to-identify-what-function-call-raise-an-exception-in-python
	"""
	tb = sys.exc_info()[-1]
	stk = traceback.extract_tb(tb, 1)
	fname = stk[0][3]
	return fname


def bamFilesFromConfig(config, orient, absolutePath):
	"""
		Return the path of the different bam files.

		:param config: The config file from conf4circos.py
		:type config: str
		:param orient: The orientation of the reads
		:type orient: str
		:param absolutePath: The absolute path of the configuration file
		:param absolutePath: str
		:return: A dic containing the path of each bam file
		:rtype: dic
	"""

	bamFiles = {}
	bamFiles["chr_ff"] = absolutePath+'/'+os.path.basename(config.get('Trie_discord', 'out_chr_ff'))
	bamFiles["chr_fr"] = absolutePath+'/'+os.path.basename(config.get('Trie_discord', 'out_chr_fr'))
	bamFiles["chr_rf"] = absolutePath+'/'+os.path.basename(config.get('Trie_discord', 'out_chr_rf'))
	bamFiles["chr_rr"] = absolutePath+'/'+os.path.basename(config.get('Trie_discord', 'out_chr_rr'))
	bamFiles["ff"] = absolutePath+'/'+os.path.basename(config.get('Trie_discord', 'out_ff'))
	bamFiles["rr"] = absolutePath+'/'+os.path.basename(config.get('Trie_discord', 'out_rr'))
	bamFiles["ins"] = absolutePath+'/'+os.path.basename(config.get('Trie_discord', 'out_ins'))
	bamFiles["del"] = absolutePath+'/'+os.path.basename(config.get('Trie_discord', 'out_del'))
	if orient == 'rf':
		bamFiles["fr"] = absolutePath+'/'+os.path.basename(config.get('Trie_discord', 'out_fr'))
	else:
		bamFiles["rf"] = absolutePath+'/'+os.path.basename(config.get('Trie_discord', 'out_rf'))
	return bamFiles


def parseCoordinates(coord):
	"""
		Return a list of 3 elements [chromosome, start_position, end_position] from the format : chr:start:end

		:param coord: The coordonates for the zone to draw
		:type coord: str
		:return: A list with three elements : chromosome name, start position, end position
		:rtype: list
	"""

	elmts = coord.split(':')
	if len(elmts) != 3:
		raise ValueError("Invalid format for the coordinates. chr:start:end")
	else:
		return [elmts[0], int(elmts[1]), int(elmts[2])]


def extractMateAlignments(locaPrograms, samfile, bamFile):
	"""
		Extract the mate alignement from a sam file.

		:return: The filename to the sam file generated or an empty string if no alignement are extracted
		:rtype: str
	"""
	f = open(samfile, 'r')
	o = open('listReads' ,'w')
	i = 0
	for line in f:
		if line.strip() and line[0] != '@':
			cols = line.split()
			o.write(cols[0]+'\n')
			i += 1
	f.close()
	o.close()

	if i:
		utils.extractSamFromReads(locaPrograms, bamFile, 'bam', "listReads", "pairReads.sam")
		return "pairReads.sam"
	else:
		return ""


def clusterizeReads(allReadsFile, minReads, chrom, start, end, maxgap, loca_programs, job):
	"""
		Clusterize reads in zones, based on a minimum gap length

		:param allReadsFile: The sam file containing the reads to clusterize
		:type allReadsFile: str
		:param minReads: The minimum number of reads to validate a cluster
		:type minReads: int
		:param chrom: the chromosome name of the start zone
		:type chrom: str
		:param start: the start position of the zone
		:type start: int
		:param end: the end position of the zone
		:type end: int
		:param maxGap: The maximal number of continuous gap accepted in a cluster
		:type maxGap: int
		:param LOCA_PROGRAMS: From the Configparser module. Contains the path of each programs
		:return: A list containing the clusters
		:rtype: list
	"""
	
	# print(job)
	
	DicoReadsInZone = {}
	readsOutZone = []
	zonesToDraw = []
	samHeader = []
	f = open(allReadsFile, 'r')
	for line in f:
		if line.strip() and line[0] != '@':
			cols = line.split()
			if cols[2] == chrom and int(cols[3]) >= start and int(cols[3]) <= end:  # The reads is in the zone
				DicoReadsInZone[cols[0]] = cols[0:3]+[int(cols[3])]+cols[4:]
			else:
				readsOutZone.append(cols[0:3]+[int(cols[3])]+cols[4:7]+[int(cols[7])]+cols[8:])
		elif line.strip():
			samHeader.append(line.strip())
	
	# extracted zones do not exactly correspond to specified boundaries: these reads should be removed
	InZone = set(DicoReadsInZone.keys())
	DestZone = set()
	for read in readsOutZone:
		DestZone.add(read[0])
	NotInBoth = InZone.symmetric_difference(DestZone)
	InBoth = InZone.intersection(DestZone)
	
	if len(InBoth) != DestZone or len(InZone) != len(InBoth):
		# Identifying reads to remove from OutZone
		ListeToRemove = []
		for i in range(len(readsOutZone)):
			if readsOutZone[i][0] in NotInBoth:
				ListeToRemove.append(i)
		for i in sorted(ListeToRemove, reverse=True):
			del readsOutZone[i]
		# Removing read from InZone (if present)
		for i in NotInBoth:
			if i in DicoReadsInZone:
				del DicoReadsInZone[i]
	
	InZone = set(DicoReadsInZone.keys())
	DestZone = set()
	for read in readsOutZone:
		DestZone.add(read[0])
	NotInBoth = InZone.symmetric_difference(DestZone)
	InBoth = InZone.intersection(DestZone)
	
	if NotInBoth:
		sys.exit('A bug occured')
	
	# print(len(InZone), len(DestZone), len(NotInBoth), len(InBoth))

	if readsOutZone and DicoReadsInZone:
		# clusterize the outZone reads
		o = open("../../cluster_"+chrom+'_'+str(start)+'_'+str(end), 'a')
		d = sorted(readsOutZone, key=itemgetter(3))
		readsOutZone = sorted(d, key=itemgetter(2))

		listReadsInZone = []
		DicoTargetForSam = {}

		clusters = [[readsOutZone[0]]]
		last = len(readsOutZone[1:]) - 1
		DicoTargetForSam[readsOutZone[0][0]] = readsOutZone[0]
		listReadsInZone.append(list(DicoReadsInZone[readsOutZone[0][0]]))
		
		for i, read in enumerate(readsOutZone[1:]):
			if read[2] == clusters[-1][-1][2] and abs(read[3] - clusters[-1][-1][3]) <= maxgap:
				clusters[-1].append(read)
				DicoTargetForSam[read[0]] = read
				listReadsInZone.append(list(DicoReadsInZone[read[0]]))
			else:  # new cluster
				# print( len(clusters[-1]))
				if len(clusters[-1]) >= minReads:  # Probable valid cluster
					# print('yes2')
					
					# cross search (to validate a query cluster also)
					d = sorted(listReadsInZone, key=itemgetter(3))
					listReadsInZone = sorted(d, key=itemgetter(2))
					
					Qclusters = [[listReadsInZone[0]]]
					Qlast = len(listReadsInZone[1:]) - 1
					
					QueryForSam = []
					TargetForSam = []
					
					QueryForSam.append('\t'.join(list(map(str, listReadsInZone[0]))))
					TargetForSam.append('\t'.join(list(map(str, DicoTargetForSam[listReadsInZone[0][0]]))))
					
					for Qi, Qread in enumerate(listReadsInZone[1:]):
						if Qread[2] == Qclusters[-1][-1][2] and abs(Qread[3] - Qclusters[-1][-1][3]) <= maxgap:
							Qclusters[-1].append(Qread)
							QueryForSam.append('\t'.join(list(map(str, Qread))))
							TargetForSam.append('\t'.join(list(map(str, DicoTargetForSam[Qread[0]]))))
						else: # New query cluster
							if len(Qclusters[-1]) >= minReads: # Valid cluster
								
								QuerySam = open('QuerySam.sam', 'w')
								QuerySam.write('\n'.join(samHeader+QueryForSam))
								QuerySam.close()
								TargetSam = open('TargetSam.sam', 'w')
								TargetSam.write('\n'.join(samHeader+TargetForSam))
								TargetSam.close()
								
								# converting sam to bam
								utils.sam2bam(loca_programs, 'QuerySam.sam', 'QuerySam.bam')
								utils.sam2bam(loca_programs, 'TargetSam.sam', 'TargetSam.bam')
								
								# sorting bam
								utils.sortBam(loca_programs, 'QuerySam.bam', 'QuerySam_sorted.bam')
								utils.sortBam(loca_programs, 'TargetSam.bam', 'TargetSam_sorted.bam')
								
								# calculating Query coverage
								utils.calcul_cov(loca_programs, 'QuerySam_sorted.bam', 'bam', 'QuerySam.cov')
								# calculating Target coverage
								utils.calcul_cov(loca_programs, 'TargetSam_sorted.bam', 'bam', 'TargetSam.cov')
								
								# calculating start and end of Query zone
								QueryZone = identOnCov('QuerySam.cov')
								# calculating start and end of Target zone
								TargetZone = identOnCov('TargetSam.cov')
								
								print(TargetZone)
					
								zonesToDraw.append(TargetZone)
								o.write('['+job+' '+' '.join(QueryZone)+' --> '+' '.join(TargetZone)+']\n')
								o.write('reads number : '+str(len(Qclusters[-1]))+'\nlength : '+str(int(TargetZone[2]) - int(TargetZone[1]))+'\n')
								for reads in Qclusters[-1]:
									o.write(reads[0]+'\n')
								o.write('\n')
				
							QueryForSam = []
							TargetForSam = []
							Qclusters.append([Qread])
							QueryForSam.append('\t'.join(list(map(str, Qread))))
							TargetForSam.append('\t'.join(list(map(str, DicoTargetForSam[Qread[0]]))))
							
						if Qi == Qlast and len(Qclusters[-1]) >= minReads:
							QuerySam = open('QuerySam.sam', 'w')
							QuerySam.write('\n'.join(samHeader+QueryForSam))
							QuerySam.close()
							TargetSam = open('TargetSam.sam', 'w')
							TargetSam.write('\n'.join(samHeader+TargetForSam))
							TargetSam.close()
							
							# converting sam to bam
							utils.sam2bam(loca_programs, 'QuerySam.sam', 'QuerySam.bam')
							utils.sam2bam(loca_programs, 'TargetSam.sam', 'TargetSam.bam')
							
							# sorting bam
							utils.sortBam(loca_programs, 'QuerySam.bam', 'QuerySam_sorted.bam')
							utils.sortBam(loca_programs, 'TargetSam.bam', 'TargetSam_sorted.bam')
							
							# calculating Query coverage
							utils.calcul_cov(loca_programs, 'QuerySam_sorted.bam', 'bam', 'QuerySam.cov')
							# calculating Target coverage
							utils.calcul_cov(loca_programs, 'TargetSam_sorted.bam', 'bam', 'TargetSam.cov')
							
							# calculating start and end of Query zone
							QueryZone = identOnCov('QuerySam.cov')
							# calculating start and end of Target zone
							TargetZone = identOnCov('TargetSam.cov')
							
							print(TargetZone)
				
							zonesToDraw.append(TargetZone)
							o.write('['+job+' '+' '.join(QueryZone)+' --> '+' '.join(TargetZone)+']\n')
							o.write('reads number : '+str(len(Qclusters[-1]))+'\nlength : '+str(int(TargetZone[2]) - int(TargetZone[1]))+'\n')
							for reads in Qclusters[-1]:
								o.write(reads[0]+'\n')
							o.write('\n')
				
				DicoTargetForSam = {}
				listReadsInZone = []
				clusters.append([read])
				DicoTargetForSam[read[0]] = read
				listReadsInZone.append(list(DicoReadsInZone[read[0]]))
				
				
			if i == last and len(clusters[-1]) >= minReads:
					
				# cross search (to validate a query cluster also)
				d = sorted(listReadsInZone, key=itemgetter(3))
				listReadsInZone = sorted(d, key=itemgetter(2))
				
				Qclusters = [[listReadsInZone[0]]]
				Qlast = len(listReadsInZone[1:]) - 1
				
				QueryForSam = []
				TargetForSam = []
				
				QueryForSam.append('\t'.join(list(map(str, listReadsInZone[0]))))
				TargetForSam.append('\t'.join(list(map(str, DicoTargetForSam[listReadsInZone[0][0]]))))
				
				for Qi, Qread in enumerate(listReadsInZone[1:]):
					if Qread[2] == Qclusters[-1][-1][2] and abs(Qread[3] - Qclusters[-1][-1][3]) <= maxgap:
						Qclusters[-1].append(Qread)
						QueryForSam.append('\t'.join(list(map(str, Qread))))
						TargetForSam.append('\t'.join(list(map(str, DicoTargetForSam[Qread[0]]))))
					else: # New query cluster
						if len(Qclusters[-1]) >= minReads: # Valid cluster
							
							QuerySam = open('QuerySam.sam', 'w')
							QuerySam.write('\n'.join(samHeader+QueryForSam))
							QuerySam.close()
							TargetSam = open('TargetSam.sam', 'w')
							TargetSam.write('\n'.join(samHeader+TargetForSam))
							TargetSam.close()
							
							# converting sam to bam
							utils.sam2bam(loca_programs, 'QuerySam.sam', 'QuerySam.bam')
							utils.sam2bam(loca_programs, 'TargetSam.sam', 'TargetSam.bam')
							
							# sorting bam
							utils.sortBam(loca_programs, 'QuerySam.bam', 'QuerySam_sorted.bam')
							utils.sortBam(loca_programs, 'TargetSam.bam', 'TargetSam_sorted.bam')
							
							# calculating Query coverage
							utils.calcul_cov(loca_programs, 'QuerySam_sorted.bam', 'bam', 'QuerySam.cov')
							# calculating Target coverage
							utils.calcul_cov(loca_programs, 'TargetSam_sorted.bam', 'bam', 'TargetSam.cov')
							
							# calculating start and end of Query zone
							QueryZone = identOnCov('QuerySam.cov')
							# calculating start and end of Target zone
							TargetZone = identOnCov('TargetSam.cov')
							
							print(TargetZone)
				
							zonesToDraw.append(TargetZone)
							o.write('['+job+' '+' '.join(QueryZone)+' --> '+' '.join(TargetZone)+']\n')
							o.write('reads number : '+str(len(Qclusters[-1]))+'\nlength : '+str(int(TargetZone[2]) - int(TargetZone[1]))+'\n')
							for reads in Qclusters[-1]:
								o.write(reads[0]+'\n')
							o.write('\n')
			
						QueryForSam = []
						TargetForSam = []
						Qclusters.append([Qread])
						QueryForSam.append('\t'.join(list(map(str, Qread))))
						TargetForSam.append('\t'.join(list(map(str, DicoTargetForSam[Qread[0]]))))
						
					if Qi == Qlast and len(Qclusters[-1]) >= minReads:
						QuerySam = open('QuerySam.sam', 'w')
						QuerySam.write('\n'.join(samHeader+QueryForSam))
						QuerySam.close()
						TargetSam = open('TargetSam.sam', 'w')
						TargetSam.write('\n'.join(samHeader+TargetForSam))
						TargetSam.close()
						
						# converting sam to bam
						utils.sam2bam(loca_programs, 'QuerySam.sam', 'QuerySam.bam')
						utils.sam2bam(loca_programs, 'TargetSam.sam', 'TargetSam.bam')
						
						# sorting bam
						utils.sortBam(loca_programs, 'QuerySam.bam', 'QuerySam_sorted.bam')
						utils.sortBam(loca_programs, 'TargetSam.bam', 'TargetSam_sorted.bam')
						
						# calculating Query coverage
						utils.calcul_cov(loca_programs, 'QuerySam_sorted.bam', 'bam', 'QuerySam.cov')
						# calculating Target coverage
						utils.calcul_cov(loca_programs, 'TargetSam_sorted.bam', 'bam', 'TargetSam.cov')
						
						# calculating start and end of Query zone
						QueryZone = identOnCov('QuerySam.cov')
						# calculating start and end of Target zone
						TargetZone = identOnCov('TargetSam.cov')
						
						print(TargetZone)
			
						zonesToDraw.append(TargetZone)
						o.write('['+job+' '+' '.join(QueryZone)+' --> '+' '.join(TargetZone)+']\n')
						o.write('reads number : '+str(len(Qclusters[-1]))+'\nlength : '+str(int(TargetZone[2]) - int(TargetZone[1]))+'\n')
						for reads in Qclusters[-1]:
							o.write(reads[0]+'\n')
						o.write('\n')
				
				
		o.close()

	return zonesToDraw


def constructZonesDesc(zonesToDraw, insertSize, chromFile, coordZone):
	"""
		Construct a string to be passed as options for the circos command. (ex : chr01:12000:20000-chr02:1000000:2000000-chr8)

		:param zonesToDraw: The clusters return by clusterizeReads()
		:type zonesToDraw: list
		:param insertSize: The median insert size
		:type insertSize: int
		:param chromFile: The file which list the chromosome and their length
		:type chromFile: str
		:param coordZone: The coordinate of the first zone, returned by parseCoordinates
		:type coordZone: list
		:return: A string formated to be passed as argument (--draw) to the draw_circos.py script
		:rtype: str
	"""
	chromLength = {}
	f = open(chromFile, 'r')
	for l in f:
		if l.strip():
			cols = l.split()
			chromLength[cols[0]] = int(cols[1])
	f.close()

	# zonesToDraw.append(coordZone)
	optionZones = coordZone[0]+":"+str(coordZone[1])+":"+str(coordZone[2]+1)
	for zone in zonesToDraw:
		start = int(zone[1]) - int(insertSize)
		if start < 0:
			start = 0
		end = int(zone[2]) + int(insertSize)
		if end > chromLength[zone[0]]:
			end = chromLength[zone[0]]
		optionZones += "-"+zone[0]+":"+str(start)+":"+str(end + 1)

	return optionZones


def worker(job):
	codeError = 0
	try:
		directory = tempfile.mkdtemp(prefix=job[0]+"_", dir=os.getcwd()).split('/')[-1]+'/' # Create a subdirectory for each process
		os.chdir(directory)
		utils.extractSamFromPosition(job[2], job[1], 'bam', job[3][0], job[3][1], job[3][2], "readsInZone.bam")
		utils.bam2sam(job[2], "readsInZone.bam", "readsInZone.sam")
		allReadsFile = extractMateAlignments(job[2], "readsInZone.sam", job[1])
		if allReadsFile:
			zonesToDraw = clusterizeReads(allReadsFile, job[4], job[3][0], job[3][1], job[3][2], job[5], job[2], job[0])
		else:
			zonesToDraw = 0
	except Exception, e:
		print ("There is an error :")
		print ("\t"+extract_function_name())
		print ("\t"+e.__doc__+" ("+e.message+" )\n")
		codeError = 1
		zonesToDraw = 0
	finally:
		os.chdir('../')
		return [codeError, zonesToDraw, job]


def __main__():
	# Parse Command Line
	parser = optparse.OptionParser(usage="python %prog [options]\n\nProgram designed by Paco Derouault : paco.derouault@gmail.com, modified by Guillaume Martin : guillaume.martin@cirad.fr")
	parser.add_option( '-z', '--zone', dest='zone', default='', help='Coordinate of the zone (ex : chr01:10000:20000).')
	parser.add_option( '-r', '--minreads', dest='minreads', default='5', help='Minimum reads to make a cluster.')
	parser.add_option( '-s', '--confsc', dest='confSc', default='', help='Path to the configuration file of scaffremodler.')
	parser.add_option( '-c', '--confci', dest='confCi', default='', help='Path to the configuration file of conf4circos.')
	parser.add_option( '-l', '--locaPrograms', dest='locaPrograms', default='', help='Path to the file containing the path of the programs.')
	parser.add_option( '-p', '--nump', dest='nump', default='', help='Number of processor to use.')
	parser.add_option( '-g', '--maxgap', dest='maxgap', default='5000', help='Maximum maxgap in pb to clusterize two reads.')
	parser.add_option( '-o', '--out', dest='out', help='Output file name.')
	(options, args) = parser.parse_args()

	if not options.zone:
		sys.exit("Please provide the coordinate of the zone.")
	if not options.minreads:
		sys.exit("Please provide a minimum number of reads to make a cluster.")
	if not options.confSc:
		sys.exit("Please join the configuration file of the scaffremodler pipeline.")
	if not options.confCi:
		sys.exit("Please join the configuration file of conf4circos.py script.")
	if options.nump:
		nbProcs = int(options.nump)
	else:
		nbProcs = 1
	if nbProcs > mp.cpu_count():
		sys.exit("Processors number too high.\nYou have only "+str(mp.cpu_count())+" processor(s) available.")

	pathname = os.path.dirname(sys.argv[0])
	loca_programs = ConfigParser.RawConfigParser()
	loca_programs.read(pathname+'/loca_programs.conf')


	configCi = ConfigParser.RawConfigParser()
	configCi.read(options.confCi)
	pathname = os.path.dirname(sys.argv[0])
	locaPrograms = ConfigParser.RawConfigParser()
	locaPrograms.read(pathname+'/loca_programs.conf')
	coordZone = parseCoordinates(options.zone)
	pathname = os.path.dirname(sys.argv[0])

	if os.path.exists(options.confSc):
		configSc = ConfigParser.RawConfigParser()
		configSc.read(options.confSc)
		absolutePath = os.path.dirname(os.path.abspath(options.confSc))
		orient = configSc.get('General', 'orient')
		insertSize = int(float(configSc.get('Calc_coverage', 'median_insert')))
		bamFiles = bamFilesFromConfig(configSc, orient, absolutePath)
		chromFile = absolutePath+'/'+configSc.get('General', 'chr').split('/')[-1]
	else:
		sys.exit("The configuration file of scaffremodler is unvailable.")


	if os.path.exists(options.confCi):
		absolutePath = os.path.dirname(options.confCi)
		karFile = absolutePath+'/'+configCi.get('General', 'out_kar')
		locNFile = absolutePath+'/'+configCi.get('General', 'out_n')
		covFile = absolutePath+'/'+configCi.get('Coverage', 'cov')
	else:
		sys.exit("The configuration file of conf4circos is unvailable.")

	listJobs = []
	
	for bamFile in bamFiles:
		if bamFiles[bamFile].split('/')[-1] != 'empty':
			listJobs.append([bamFile, bamFiles[bamFile], locaPrograms, coordZone, int(options.minreads), int(options.maxgap), options.confCi, insertSize])

	# create a sub directory to work
	workingDir = tempfile.mkdtemp(prefix=options.zone.replace(":", "-")+"_", dir=os.getcwd()).split('/')[-1]+'/'
	os.chdir(workingDir)
	
	pool = mp.Pool(processes=nbProcs)
	results = pool.map(worker, listJobs)

	os.chdir('../')
	shutil.rmtree(workingDir)

	zonesToDraw = []
	error = False
	for job in results:
		if not job[0] and job[1]:  # no error and cluster found
			for zone in job[1]:
				zonesToDraw.append(zone)
		elif job[0]:
			error = True
			print ("Error in the job : "+', '.join(map(str, job[2])))

	if not error:
		if options.out:
			outputName = options.out
		else:
			outputName = coordZone[0]+"_"+str(coordZone[1])+"_"+str(coordZone[2])+".png"

		optionZones = constructZonesDesc(zonesToDraw, insertSize, chromFile, coordZone)
		print optionZones
		drawCircos = "%s %s --config %s --out %s --draw %s --cov y --discord y --scaff n --text n --read_fr y --read_ff y --read_rf y --read_rr y --read_ins y --read_delet y --read_chr_ff y --read_chr_fr y --read_chr_rf y --read_chr_rr y" % (locaPrograms.get('Programs','python'), pathname+'/draw_circos.py', options.confCi, outputName, optionZones)
		utils.run_job(getframeinfo(currentframe()), drawCircos, "Error in drawCircos", True)


if __name__ == "__main__": __main__()
