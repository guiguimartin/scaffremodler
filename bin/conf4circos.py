#!/usr/bin/env python
# -*- coding:Utf-8 -*-
#
#  Copyright 2014 CIRAD
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, see <http://www.gnu.org/licenses/> or
#  write to the Free Software Foundation, Inc.,
#  51 Franklin Street, Fifth Floor, Boston,
#  MA 02110-1301, USA.
#
#

# -*- coding: utf-8 -*-
import optparse, os, shutil, subprocess, sys, tempfile, fileinput, ConfigParser, operator, time, math, multiprocessing, datetime, re
from Bio.Seq import Seq
from Bio.Alphabet import generic_dna
from Bio import SeqIO
from Bio.SeqRecord import SeqRecord
from operator import itemgetter

def stop_err( msg ):
	sys.stderr.write( "%s\n" % msg )
	sys.exit()

def run_job (cmd_line, ERROR):
	print cmd_line
	try:
		tmp = (tempfile.NamedTemporaryFile().name)+'.error'
		# print tmp
		error = open(tmp, 'w')
		proc = subprocess.Popen( args=cmd_line, shell=True, stderr=error)
		returncode = proc.wait()
		error.close()
		error = open( tmp, 'rb' )
		stderr = ''
		buffsize = 1048576
		try:
			while True:
				stderr += error.read( buffsize )
				if not stderr or len( stderr ) % buffsize != 0:
					break
		except OverflowError:
			pass
		error.close()
		os.remove(tmp)
		if returncode != 0:
			raise Exception, stderr
	except Exception, e:
		stop_err( ERROR + str( e ) )


def checkFileExist(fname):
	"""
		Check the existence of a file.

		:param fname: the path to the file to checkFileExist
		:type fname: str
		:return: A boolean with true if the file existe, or false if the file doesn't exist.
		:rtype: bool
	"""

	try:
		f = open(fname,'r')
		f.close()
		return 1
	except:
		return 0


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


def parseConfFile(confFile):
	if checkFileExist(confFile):
		listPath = {}
		f = open(confFile, 'r')
		for line in f:
			if line.strip():
				cols = re.split("=|:", line.strip())
				if len(cols) != 2:
					raise ValueError("Error in the configuration file : "+confFile+". The key "+cols[0]+" doesn't have a value.")
				else:
					disc = cols[0].strip()
					path = cols[1].strip()
					if checkFileExist(path):
						if disc == 'fr' or disc == 'rf':
							disc = 'frf'
						listPath[disc] = path
					else:
						raise IOError("The file "+path+" is not found.")
	else:
		raise IOError("The configuration File : "+confFile+" is not found.")

	return listPath


def zonesOverlap(zonesOrg, zonesToRemove):
	"""
		Calculate the overlap of one couple of zone with all the zones of one accession.

		:param zonesOrg: The mate zone to test.
		:type zonesOrg: list
		:param zonesToRemove: The zones of one accession
		:type zonesToRemove: list
		:return: A list with three boolean. first : indicate if the zoneOrg is overlapping one zone of zonesToRemove; The second indicate if the overlapping zone is tagged as "PASSED" or not. The third indicate if the overlapping zone is tagged as "NOT_PASSED" or not.
		:rtype: list
	"""
	i = 0
	j = len(zonesToRemove)
	m = (i + j) // 2

	overlap = False

	zoneT = []

	amontChr = zonesOrg[0]
	amontStart = int(zonesOrg[1])
	amontEnd = int(zonesOrg[2])

	avalChr = zonesOrg[3]
	AvalStart = int(zonesOrg[4])
	AvalEnd = int(zonesOrg[5])

	while i < j and not overlap:

		if zonesToRemove[m][0] == amontChr:

			k = m
			while k >= i and zonesToRemove[k][0] == amontChr:

				if amontStart <= int(zonesToRemove[k][2]) and amontEnd >= int(zonesToRemove[k][1]) and AvalStart <= int(zonesToRemove[k][5]) and AvalEnd >= int(zonesToRemove[k][4]) and zonesToRemove[k][3] == avalChr:
					overlap = True
					zoneT = [zonesToRemove[k][0], zonesToRemove[k][1], zonesToRemove[k][2], zonesToRemove[k][3], zonesToRemove[k][4], zonesToRemove[k][5]]
				k -= 1

			k = m + 1
			while k < j and zonesToRemove[k][0] == amontChr:

				if amontStart <= int(zonesToRemove[k][2]) and amontEnd >= int(zonesToRemove[k][1]) and AvalStart <= int(zonesToRemove[k][5]) and AvalEnd >= int(zonesToRemove[k][4]) and zonesToRemove[k][3] == avalChr:
					overlap = True
					zoneT = [zonesToRemove[k][0], zonesToRemove[k][1], zonesToRemove[k][2], zonesToRemove[k][3], zonesToRemove[k][4], zonesToRemove[k][5]]
				k += 1

			# no infinite loop
			if not overlap:
				break

		elif zonesToRemove[m][0] < amontChr:
			i = m + 1
		else:
			j = m

		m = (i + j)//2

	return [overlap, zoneT]


def readZonesToRemove(removedZones):
	"""
		Read from a file the zone to remove.

		:param removedZones: path of a file containing the zones to remove.
		:type removedZones: str:
		:return: A list containing the zones.
		:rtype: list
	"""

	zonesToRemove = []
	try:
		f = open(removedZones, 'r')
	except Exception as e:
		print ("There is an error :")
		print ("\t"+extract_function_name())
		print ("\t"+e.__doc__+" ("+e.message+" )\n")

	for line in f:
		if line.strip() and line[0] != '#':
			cols = line.split()
			zonesToRemove.append([cols[0], int(cols[1]), int(cols[2]), cols[5], int(cols[6]), int(cols[7])])
	f.close()

	return sorted(zonesToRemove, key = lambda x : (x[0], x[3], x[1]))


def convertFilter(filter, contrary = False):
	if not contrary:
		if filter == 'P' or filter == "PASSED":
			filter = 3
		elif filter == "NP" or filter == "NOT_PASSED":
			filter = 2
		elif filter == 'N' or filter == "NEW_PASSED":
			filter = 1
		else:
			filter = 0
	else:
		if filter == 3:
			filter = 'P'
		elif filter == 2:
			filter = 'NP'
		elif filter == 1:
			filter = 'N'
		else:
			filter = 'N'
	return filter

def create_kar(REF, CHR, OUT_KAR, OUT_N):
	record_dict = SeqIO.index(REF, "fasta")
	file = open(CHR)
	out1 = open(OUT_KAR,'w')
	for line in file:
		data = line.split()
		if data:
			out1.write("chr - "+data[0]+ " "+data[0]+" 0 "+str(len(str(record_dict[data[0]].seq))+1)+" blue\n")
	file.close()

	out2 = open(OUT_N,'w')
	file = open(CHR)
	for line in file:
		data = line.split()
		if data:
			sequence = str(record_dict[data[0]].seq)
			pos = 0
			debut = 0
			sur_N = 0
			if sequence[0] == 'N' or sequence[0] == 'n':
				raise ValueError('the program cannot work because sequence '+data[0]+' begins with N')
			elif sequence[-1] == 'N' or sequence[-1] == 'n':
				raise ValueError('the program cannot work because sequence '+data[0]+' ends with N')
			out2.write(data[0]+'\t'+str(pos+1)+'\t'+str(pos+1)+'\t'+data[0]+'-'+str(pos+1)+'-'+'p\n')
			for n in sequence:
				if n == 'N' or n == 'n':
					if not(sur_N):
						sur_N = 1
						debut = pos
						out2.write(data[0]+'\t'+str(pos)+'\t'+str(pos)+'\t'+data[0]+'-'+str(pos)+'-'+'v\n')
				elif sur_N:
					sur_N = 0
					out1.write('band '+data[0]+' p36.33 p36.33 '+str(debut)+' '+str(pos+1)+' black\n')
					out2.write(data[0]+'\t'+str(pos+1)+'\t'+str(pos+1)+'\t'+data[0]+'-'+str(pos+1)+'-'+'p\n')
				pos += 1
			out2.write(data[0]+'\t'+str(pos)+'\t'+str(pos)+'\t'+data[0]+'-'+str(pos)+'-'+'f\n')
	out1.close()
	out2.close()
	return 0
##########################################################################################################################################################
#fonction that create link file based on discordant zone
def create_discord_link_org(FILE, OUT):
	outfile = open(OUT,'w')
	i = 1
	file = open(FILE)
	for line in file:
		data = line.split()
		if data:
			if data[0][0] != "#":
				if data[13] == 'PASSED':
					if i == 1:
						# outfile.write('link'+str(i)+' '+data[0]+' '+data[1]+' '+data[2]+'\n')
						# outfile.write('link'+str(i)+' '+data[5]+' '+data[6]+' '+data[7])
						outfile.write(data[0]+' '+data[1]+' '+data[2]+' '+data[5]+' '+data[6]+' '+data[7]+'\n')
						i = i + 1
					else:
						# outfile.write('\nlink'+str(i)+' '+data[0]+' '+data[1]+' '+data[2])
						# outfile.write('\nlink'+str(i)+' '+data[5]+' '+data[6]+' '+data[7])
						outfile.write(data[0]+' '+data[1]+' '+data[2]+' '+data[5]+' '+data[6]+' '+data[7]+'\n')
						i = i + 1
	outfile.close()
	return 0

def create_discord_link(scoreFile, outFile, intervalNbAcc, filterZone, filterDraw, removedZones):
	"""
		Create a link file based on the discordant zones.

		:param scoreFile: the score file provide by the script "7_select_on_cov.py"
		:type scoreFile: str
		:param outFile: the .link outfile
		:type outFile: str
		:param nbAccessMin: the minimum number of accession where a couple of zones is present. 0 = the zone is specific to the accession.
		:type nbAccessMin: int
		:param filterZone: The filter used to compare couple of zones. (PASSED, NOT_PASSED or NEW_PASSED)
		:type filterZone: str
		:param removedZones: File containing a list of zones not to be considered.
		:type removedZones: str
		:return: void
	"""

	if removedZones:
		zonesToRemove = readZonesToRemove(removedZones)

	output = open(outFile, 'w')
	input = open(scoreFile, 'r')

	filterZone = convertFilter(filterZone)
	filterDraw = convertFilter(filterDraw)

	if intervalNbAcc != "null":
		# treatment of the interval
		intervalNbAcc = intervalNbAcc.split('-')
		if not intervalNbAcc:
			raise valueError("Invalid interval of accession number : "\
								 +str(intervalNbAcc)+\
								 ". Please format the interval like : 0-3")
		else:
			intervalNbAcc[0] = int(intervalNbAcc[0])
			if len(intervalNbAcc) == 1:
				intervalNbAcc.append(intervalNbAcc[0])
			elif len(intervalNbAcc) == 2:
				intervalNbAcc[1] = int(intervalNbAcc[1])
			else:
				raise valueError("Invalid interval of accession number : "\
								 +str(intervalNbAcc)+\
								 ". Please format the interval like : 0-3")
	i = 0
	for line in input:
		cols = line.split()
		if cols and cols[0][0] != '#' and convertFilter(cols[13]) >= filterDraw:  # not header
			if intervalNbAcc != "null":
				nbAccessionVal = 0
				if cols[10] != '-':
					for accession in cols[10].split('|'):
						elmts = accession.split(':')
						if filterZone <= int(elmts[1]):  #Identical zones found in another accession
							nbAccessionVal += 1
				if nbAccessionVal >= intervalNbAcc[0] and nbAccessionVal <= intervalNbAcc[1]:

					if removedZones:
						if not zonesOverlap([cols[0], int(cols[1]), int(cols[2]), cols[5], int(cols[6]), int(cols[7])], zonesToRemove):
							# output.write("link"+str(i)+' '+cols[0]+' '+cols[1]+' '+cols[2]+"\
							# 			 \nlink"+str(i)+' '+cols[5]+' '+cols[6]+' '+cols[7]+'\n')
							output.write(cols[0]+' '+cols[1]+' '+cols[2]+' '+cols[5]+' '+cols[6]+' '+cols[7]+ \
							' url=chr1='+cols[0]+'/start1='+cols[1]+'/end1='+cols[2]+'/size1='+cols[3]+'/cov1='+cols[4]+\
							'/chr2='+cols[5]+'/start2='+cols[6]+'/end2='+cols[7]+'/size2='+cols[8]+'/cov2='+cols[9]+\
							'/reads='+cols[11]+'/misc='+cols[10]+'\n')
						i += 1
					else:
						# output.write("link"+str(i)+' '+cols[0]+' '+cols[1]+' '+cols[2]+"\
						# 			 \nlink"+str(i)+' '+cols[5]+' '+cols[6]+' '+cols[7]+'\n')
						output.write(cols[0]+' '+cols[1]+' '+cols[2]+' '+cols[5]+' '+cols[6]+' '+cols[7]+ \
						' url=chr1='+cols[0]+'/start1='+cols[1]+'/end1='+cols[2]+'/size1='+cols[3]+'/cov1='+cols[4]+\
						'/chr2='+cols[5]+'/start2='+cols[6]+'/end2='+cols[7]+'/size2='+cols[8]+'/cov2='+cols[9]+\
						'/reads='+cols[11]+'/misc='+cols[10]+'\n')
			else:
				if removedZones:
						overlapfound = zonesOverlap([cols[0], int(cols[1]), int(cols[2]), cols[5], int(cols[6]), int(cols[7])], zonesToRemove)

						if not overlapfound[0]:
							# output.write("link"+str(i)+' '+cols[0]+' '+cols[1]+' '+cols[2]+"\
							# 			 \nlink"+str(i)+' '+cols[5]+' '+cols[6]+' '+cols[7]+'\n')
							output.write(cols[0]+' '+cols[1]+' '+cols[2]+' '+cols[5]+' '+cols[6]+' '+cols[7]+ \
							' url=chr1='+cols[0]+'/start1='+cols[1]+'/end1='+cols[2]+'/size1='+cols[3]+'/cov1='+cols[4]+\
							'/chr2='+cols[5]+'/start2='+cols[6]+'/end2='+cols[7]+'/size2='+cols[8]+'/cov2='+cols[9]+\
							'/reads='+cols[11]+'/misc='+cols[10]+'\n')
						i += 1
				else:
					# output.write("link"+str(i)+' '+cols[0]+' '+cols[1]+' '+cols[2]+"\
					# 			 \nlink"+str(i)+' '+cols[5]+' '+cols[6]+' '+cols[7]+'\n')
					output.write(cols[0]+' '+cols[1]+' '+cols[2]+' '+cols[5]+' '+cols[6]+' '+cols[7]+ \
					' url=chr1='+cols[0]+'/start1='+cols[1]+'/end1='+cols[2]+'/size1='+cols[3]+'/cov1='+cols[4]+\
					'/chr2='+cols[5]+'/start2='+cols[6]+'/end2='+cols[7]+'/size2='+cols[8]+'/cov2='+cols[9]+\
					'/reads='+cols[11]+'/misc='+cols[10]+'\n')
				i += 1

	return 0



##########################################################################################################################################################
#fonction that create paired-read link file based on .list file of ApMap
def create_read_link(FILE, OUT, TYPE):
	#create_read_link(options.liste_read, options.prefix+'_read_rf.link', 'ok')
	outfile = open(OUT,'w')
	i = 1
	file = open(FILE)
	for line in file:
		data = line.split()
		if data:
			if data[5] == 'discard':
				if data[6] == TYPE:
					# outfile.write('link'+str(i)+' '+data[3]+' '+data[1]+' '+data[1]+\
					# 			  '\nlink'+str(i)+' '+data[4]+' '+data[2]+' '+data[2]+'\n')
					outfile.write(data[3]+' '+data[1]+' '+data[1]+' '+data[4]+' '+data[2]+' '+data[2]+'\n')
					i = i + 1
			else:
				if data[5] == TYPE:
					# outfile.write('link'+str(i)+' '+data[3]+' '+data[1]+' '+data[1]+\
					# 			  '\nlink'+str(i)+' '+data[4]+' '+data[2]+' '+data[2]+'\n')
					outfile.write(data[3]+' '+data[1]+' '+data[1]+' '+data[4]+' '+data[2]+' '+data[2]+'\n')
					i = i + 1
	outfile.close()
	return 0

##########################################################################################################################################################
#fonction that calculate coverage over a certain windows size on the reference

def mediane(LISTE):
	L = sorted(LISTE)
	N = len(L)
	n = N/2.0
	p = int(n)
	if n == 1:
		return (L[0])
	elif n == p:
		return (L[p-1]+L[p])/2.0
	else:
		return L[p]

def moyenne(L):
	if len(L) == 0:
		moyenne = 0
	else:
		print float(len(L))
		moyenne = sum(L)/float(len(L))
	return moyenne


def calcul_couv_moy(covFile, chrFile, window, output):
	"""
		Calculate the median and the mean coverage per window
	"""
	chrSize = {}
	with open(chrFile, 'r') as f:
		for line in f:
			if line.strip():
				cols = line.split()
				chrSize[cols[0]] = int(cols[1])
	i = 0
	covPerWin = []
	listWindows = []
	chr = ""
	coverage = 0.0
	index = 0
	window = int(window)
	f = open(covFile, 'r')
	for line in f:
		if line.strip():
			i += 1
			cols = line.split()
			if not chr:  # first line
				chr = cols[0]
				while i < int(cols[1]):
					index += 1
					if index == window:
						covPerWin.append(coverage/float(index))
						listWindows.append([chr, i-index, i, coverage/float(index)])
						index = 0
						coverage = 0.0
					i += 1
				coverage = float(cols[2])
				index += 1
				if index == window:
					covPerWin.append(coverage/float(index))
					listWindows.append([chr, i-index, i, coverage/float(index)])
					coverage = 0.0
					index = 0
			elif chr == cols[0]:  # same chromosome
				while i < int(cols[1]):
					index += 1
					if index == window:
						covPerWin.append(coverage/float(index))
						listWindows.append([chr, i-index, i, coverage/float(index)])
						index = 0
						coverage = 0.0
					i += 1
				coverage += float(cols[2])
				index += 1
				if index == window:
					covPerWin.append(coverage/float(index))
					listWindows.append([chr, i-index, i, coverage/float(index)])
					coverage = 0.0
					index = 0
			else:  # new chromosome
				while i <= chrSize[chr]:
					index += 1
					if index == window:
						covPerWin.append(coverage/float(index))
						listWindows.append([chr, i-index, i, coverage/float(index)])
						coverage = 0.0
						index = 0
					i += 1
				if index > 1:
					print ('index restant 1 :'+str(index))
					covPerWin.append(coverage/float(index-1))
					listWindows.append([chr, i-index, i, coverage/float(index)])
					coverage = 0.0
					index = 0
				else:
					coverage = 0.0
					index = 0
				i = 1
				chr = cols[0]
				while i < int(cols[1]):
					index += 1
					if index == window:
						covPerWin.append(coverage/float(index))
						listWindows.append([chr, i-index, i, coverage/float(index)])
						coverage = 0.0
						index = 0
					i += 1
				coverage += float(cols[2])
				index += 1
				if index == window:
					covPerWin.append(coverage/float(index))
					listWindows.append([chr, i-index, i, coverage/float(index)])
					coverage = 0.0
					index = 0
				chr = cols[0]
	f.close()

	# try:
	# 	med = mediane(covPerWin)
	# except Exception as e:
	# 	print ('oups1')
	# 	print e
	# 	sys.stdout.flush()
	# 	raise ValueError('Error in mediane()')
	#
	# listCov = []
	# out = open(output, 'w')
	# for window in listWindows:
	# 	out.write(window[0]+'\t'+str(window[1])+'\t'+str(window[2]-1)+'\t'+str(window[3] - med)+'\n')
	# 	listCov.append(window[3] - med)
	# out.close()
	#
	# try:
	# 	med = moyenne(listCov)
	# except Exception as e:
	# 	print ('oups2')
	# 	print e
	# 	sys.stdout.flush()
	# 	raise ValueError('Error in moyenne()')
	med = mediane(covPerWin)

	listCov = []
	out = open(output, 'w')
	for window in listWindows:
		out.write(window[0]+'\t'+str(window[1])+'\t'+str(window[2]-1)+'\t'+str(window[3] - med)+'\n')
		listCov.append(window[3] - med)
	out.close()

	return [med, moyenne(listCov)]

	return [med, moyenne(listCov)]

def create_tile(FILE, OUT):
	outfile = open(OUT, 'w')
	file = open(FILE)
	mot = 'color=black'
	for line in file:
		data = line.split()
		if data:
			if data[0][0] != '#':
				if data[4] == 'W':
					outfile.write(data[0]+'\t'+data[1]+'\t'+data[2]+'\t'+mot+'\n')
					if mot == 'color=black':
						mot = 'color=yellow'
					else:
						mot = 'color=black'
	file.close()
	outfile.close()
	return 0


def worker(job):
	codeError = 0
	rslt = 0
	try:
		if job[0] == "create_kar":
			rslt = create_kar(*job[1])
		elif job[0] == "calcul_couv_moy":
			rslt = calcul_couv_moy(*job[1])
		elif job[0] == "create_discord_link":
			rslt = create_discord_link(*job[1])
		elif job[0] == "create_read_link":
			rslt = create_read_link(*job[1])
		elif job[0] == "create_tile":
			rslt = create_tile(*job[1])
		elif job[0] == "create_housekeeping":
			rslt = create_housekeeping(*job[1])
		else:
			codeError = 1
			rslt = 0
			print "unrecognised function name : "+job[0]
	except Exception, e:
		print "error : "+e.__doc__+" ('"+e.message+")' in '"+job[0]+"'"
		rslt = 0
		codeError = 1
	finally:
		return [codeError, rslt, job[0], job[1]]


def create_housekeeping(fileName):

	"""
		Create the housekepping.conf file (needed if many point are drawn)

		:param PREFIX: Prefix of the output file.
		:type PREFIX: str
		:return: the housekeeping.conf file
		:rtype: void
	"""

	outfile = open(fileName,'w')
	outfile.write('anglestep       = 0.5\n')
	outfile.write('minslicestep    = 10\n')
	outfile.write('beziersamples   = 40\n')
	outfile.write('debug           = no\n')
	outfile.write('warnings        = no\n')
	outfile.write('imagemap        = no\n')
	outfile.write('paranoid        = yes\n')
	outfile.write('units_ok        = bupr\n')
	outfile.write('units_nounit    = n\n')
	outfile.write('file_delim = \s\n')
	outfile.write('file_delim_collapse = yes\n')
	outfile.write('list_record_delim = \s*[;,]\s*\n')
	outfile.write('list_field_delim  = \s*[:=]\s*\n')
	outfile.write('options_record_delim = [,;]\n')
	outfile.write('options_field_delim  = =\n')
	outfile.write('skip_missing_expression_vars = no\n')
	outfile.write('legacy_underline_expression_syntax = no\n')
	outfile.write('svg_font_scale = 1.3\n')
	outfile.write('sup_baseline_shift = 40\n')
	outfile.write('sub_baseline_shift = -40\n')
	outfile.write('sup_fontsize = 90\n')
	outfile.write('sub_fontsize = 90\n')
	outfile.write('default_font   = default\n')
	outfile.write('default_font_name  = Arial\n')
	outfile.write('default_font_color = black\n')
	outfile.write('default_color  = black\n')
	outfile.write('<guides>\n')
	outfile.write('thickness      = 1\n')
	outfile.write('size           = 5\n')
	outfile.write('type           = outline\n')
	outfile.write('<object>\n')
	outfile.write('all            = no\n')
	outfile.write('ideogram       = no\n')
	outfile.write('ideogram_label = no\n')
	outfile.write('</object>\n')
	outfile.write('<color>\n')
	outfile.write('default = lblue\n')
	outfile.write('text    = red\n')
	outfile.write('</color>\n')
	outfile.write('</guides>\n')
	outfile.write('debug_group = summary,output\n')
	outfile.write('debug_auto_timer_report = 30\n')
	outfile.write('debug_word_separator = " "\n')
	outfile.write('debug_undef_text     = _undef_\n')
	outfile.write('debug_empty_text     = _emptylist_\n')
	outfile.write('debug_validate       = yes\n')
	outfile.write('debug_output_tidy    = no\n')
	outfile.write('text_pixel_subsampling = 1\n')
	outfile.write('text_snuggle_method    = array\n')
	outfile.write('restrict_parameter_names = no\n')
	outfile.write('case_sensitive_parameter_names = no\n')
	outfile.write('calculate_track_statistics = yes\n')
	outfile.write('color_cache_static = yes\n')
	outfile.write('color_cache_file   = circos.colorlist\n')
	outfile.write('color_lists_use    = yes\n')
	outfile.write('memoize = yes\n')
	outfile.write('quit_on_dump = yes\n')
	outfile.write('offsets = 0,0\n')
	outfile.write('max_ticks            = 5000\n')
	outfile.write('max_ideograms        = 200\n')
	outfile.write('max_links            = 1000000\n')
	outfile.write('max_points_per_track = 1000000\n')
	outfile.write('undefined_ideogram = skip\n')
	outfile.write('relative_scale_iterations = 10\n')
	outfile.write('relative_scale_spacing    = mode\n')
	outfile.write('data_out_of_range = trim,warn #\n')
	outfile.write('track_defaults = etc/tracks\n')
	outfile.write('round_brush_use           = yes\n')
	outfile.write('round_brush_min_thickness = 5\n')
	outfile.write('anti_aliasing = yes\n')
	outfile.write('housekeeping = yes\n')
	outfile.write('auto_eval = no\n')
	outfile.close()


def __main__():
	t0 = datetime.datetime.now()
	#Parse Command Line
	parser = optparse.OptionParser(usage="python %prog [options]\n\nProgram designed by Guillaume MARTIN : guillaume.martin@cirad.fr\n\n"
	"This program takes in input all files needed to generate circos and output severals files that will be used to generate different circos plus a config file")

	# Wrapper options.
	#For input

	parser.add_option( '', '--ref', dest='ref', default='not_filled', help='The multi-fasta reference file')
	parser.add_option( '', '--chr', dest='chr', default='not_filled', help='File containing col1: chromosome name and col2: chromsome size')
	parser.add_option( '', '--orient', dest='orient', default='rf', help='The expected orientation: rf or fr, [default: %default]')

	parser.add_option( '', '--cov', dest='cov', default='not_filled', help='The coverage file')
	parser.add_option( '', '--window', dest='window', default=1000, help='Window size (base pair), [default: %default]')

	parser.add_option( '', '--frf', dest='frf', default='not_filled', help='frf_discord.score file')
	parser.add_option( '', '--ff', dest='ff', default='not_filled', help='ff_discord.score file')
	parser.add_option( '', '--rr', dest='rr', default='not_filled', help='rr_discord.score file')
	parser.add_option( '', '--ins', dest='ins', default='not_filled', help='ins_discord.score file')
	parser.add_option( '', '--delet', dest='delet', default='not_filled', help='delet_discord.score file')
	parser.add_option( '', '--chr_rr', dest='chr_rr', default='not_filled', help='chr_rr_discord.score file')
	parser.add_option( '', '--chr_rf', dest='chr_rf', default='not_filled', help='chr_rf_discord.score file')
	parser.add_option( '', '--chr_ff', dest='chr_ff', default='not_filled', help='chr_ff_discord.score file')
	parser.add_option( '', '--chr_fr', dest='chr_fr', default='not_filled', help='chr_fr_discord.score file')

	parser.add_option( '', '--liste_read', dest='liste_read', default='not_filled', help='A file containing information on mapped reads (.list file of ApMap)')

	parser.add_option( '', '--dis_prop', dest='dis_prop', default='not_filled', help='The file containing proportions of discordant reads (.prop file of ApMap)')

	parser.add_option( '', '--agp', dest='agp', default='not_filled', help='An agp file locating scaffold along chromosomes')

	parser.add_option( '', '--nbaccess', dest='nbaccess', default='null', help='Draw only zone presents from n accessions, [default: %default]')
	parser.add_option( '', '--filterzone', dest='filterzone', default='P', help='The filter to define a similar zone found in other accessions. Possible values : P : passed, NP : not_passed, N : New zone identified by reads only, [default: %default]')
	parser.add_option( '', '--filterdraw', dest='filterdraw', default='P', help='The filter applied on accession zone status to draw zone. Possible values : P : passed, NP : not_passed, N : New zone identified by reads only, [default: %default]')
	parser.add_option( '', '--removedZones', dest='removedZones', default='', help='File containing zones to remove.')

	# For output
	parser.add_option( '', '--prefix', dest='prefix', default='not_filled', help='Prefix for all output files. If this options is passed, all others output options are ignored, [default: %default]')

	# If no prefix arguments are passed
	parser.add_option( '', '--out_kar', dest='out_kar', default='circos_karyotype.txt', help='Karyotype output file, [default: %default]')
	parser.add_option( '', '--out_N', dest='out_N', default='circos_loc_N.txt', help='File name of text file locating N, [default: %default]')
	parser.add_option( '', '--out_H', dest='out_H', default='circos_housekeeping.txt', help='File name of housekeeping file, [default: %default]')

	parser.add_option( '', '--out_cov', dest='out_cov', default='circos_mean.cov', help='Mean coverage output file, [default: %default]')

	parser.add_option( '', '--out_frf', dest='out_frf', default='circos_zone_frf.link', help='A link output file name corresponding to frf_discord.score, [default: %default]')
	parser.add_option( '', '--out_ff', dest='out_ff', default='circos_zone_ff.link', help='A link output file name corresponding to ff_discord.score, [default: %default]')
	parser.add_option( '', '--out_rr', dest='out_rr', default='circos_zone_rr.link', help='A link output file name corresponding to rr_discord.score, [default: %default]')
	parser.add_option( '', '--out_ins', dest='out_ins', default='circos_zone_ins.link', help='A link output file name corresponding to ins_discord.score, [default: %default]')
	parser.add_option( '', '--out_delet', dest='out_delet', default='circos_zone_delet.link', help='A link output file name corresponding to delet_discord.score, [default: %default]')
	parser.add_option( '', '--out_chr_rr', dest='out_chr_rr', default='circos_zone_chr_rr.link', help='A link output file name corresponding to chr_rr_discord.score, [default: %default]')
	parser.add_option( '', '--out_chr_rf', dest='out_chr_rf', default='circos_zone_chr_rf.link', help='A link output file name corresponding to chr_rf_discord.score, [default: %default]')
	parser.add_option( '', '--out_chr_ff', dest='out_chr_ff', default='circos_zone_chr_ff.link', help='A link output file name corresponding to chr_ff_discord.score, [default: %default]')
	parser.add_option( '', '--out_chr_fr', dest='out_chr_fr', default='circos_zone_chr_fr.link', help='A link output file name corresponding to chr_fr_discord.score, [default: %default]')

	parser.add_option( '', '--Rout_rf', dest='Rout_rf', default='circos_read_rf.link', help='A link output file name corresponding to mapped fr reads, [default: %default]')
	parser.add_option( '', '--Rout_fr', dest='Rout_fr', default='circos_read_fr.link', help='A link output file name corresponding to mapped rf reads, [default: %default]')
	parser.add_option( '', '--Rout_ff', dest='Rout_ff', default='circos_read_ff.link', help='A link output file name corresponding to mapped ff reads, [default: %default]')
	parser.add_option( '', '--Rout_rr', dest='Rout_rr', default='circos_read_rr.link', help='A link output file name corresponding to mapped rr reads, [default: %default]')
	parser.add_option( '', '--Rout_ins', dest='Rout_ins', default='circos_read_ins.link', help='A link output file name corresponding to mapped ins reads, [default: %default]')
	parser.add_option( '', '--Rout_delet', dest='Rout_delet', default='circos_read_delet.link', help='A link output file name corresponding to mapped delet reads, [default: %default]')
	parser.add_option( '', '--Rout_chr_rr', dest='Rout_chr_rr', default='circos_read_chr_rr.link', help='A link output file name corresponding to mapped chr_rr reads, [default: %default]')
	parser.add_option( '', '--Rout_chr_rf', dest='Rout_chr_rf', default='circos_read_chr_rf.link', help='A link output file name corresponding to mapped chr_rf reads, [default: %default]')
	parser.add_option( '', '--Rout_chr_ff', dest='Rout_chr_ff', default='circos_read_chr_ff.link', help='A link output file name corresponding to mapped chr_ff reads, [default: %default]')
	parser.add_option( '', '--Rout_chr_fr', dest='Rout_chr_fr', default='circos_read_chr_fr.link', help='A link output file name corresponding to mapped chr_fr reads, [default: %default]')

	parser.add_option( '', '--out_scaff', dest='out_scaff', default='circos_scaffold.tile', help='A tile output file name corresponding to scaffolds, [default: %default]')

	parser.add_option( '', '--output', dest='output', default='config_circos.conf', help='The output of the conf file, [default: %default]')

	parser.add_option( '', '--thread', dest='thread', default='1', help='The number of threads to use, [default: %default]')

	(options, args) = parser.parse_args()

	nbProcs = int(options.thread)
	if nbProcs > multiprocessing.cpu_count():
		sys.exit("Processors number too high.\nYou have only "+str(multiprocessing.cpu_count())+" processor(s) available on this computer.")

	listJobs = []  # A list of all jobs

	if options.ref == 'not_filled':
		sys.exit('--ref argument is missing')
	if options.chr == 'not_filled':
		sys.exit('--chr argument is missing')

	if options.prefix != 'not_filled':
		output1 = options.prefix+'_karyotype.txt'
		output2 = options.prefix+'_loc_N.txt'
		hkFile = options.prefix+'_housekeeping.conf'
	else:
		output1 = options.out_kar
		output2 = options.out_N
		hkFile = options.out_H

	listJobs.append(["create_kar", [options.ref, options.chr, output1, output2]])
	listJobs.append(["create_housekeeping", [hkFile]])

	if options.cov != 'not_filled':
		if options.window == 'not_filled':
			sys.exit('--window argument is missing')
		if options.out_cov == 'not_filled':
			sys.exit('--out_cov argument is missing')
		if options.prefix != 'not_filled':
			output = options.prefix+'_mean.cov'
		else:
			output = options.out_cov
		listJobs.append(["calcul_couv_moy", [options.cov, options.chr, float(options.window), output]])
	if options.removedZones:
		pathToScoreFiles = parseConfFile(options.removedZones)
	else:
		pathToScoreFiles = 0

	if options.frf != 'not_filled':
		if options.prefix != 'not_filled':
			output = options.prefix+'_zone_frf.link'
		else:
			output = options.out_frf
		if options.removedZones:
			removedZones = pathToScoreFiles['frf']
		else:
			removedZones = 0
		listJobs.append(["create_discord_link", [options.frf, output, options.nbaccess, options.filterzone, options.filterdraw, removedZones]])

	if options.ff != 'not_filled':
		if options.prefix != 'not_filled':
			output = options.prefix+'_zone_ff.link'
		else:
			output = options.out_ff
		if options.removedZones:
			removedZones = pathToScoreFiles['ff']
		else:
			removedZones = 0
		listJobs.append(["create_discord_link", [options.ff, output, options.nbaccess, options.filterzone, options.filterdraw, removedZones]])

	if options.rr != 'not_filled':
		if options.prefix != 'not_filled':
			output = options.prefix+'_zone_rr.link'
		else:
			output = options.out_rr
		if options.removedZones:
			removedZones = pathToScoreFiles['rr']
		else:
			removedZones = 0
		listJobs.append(["create_discord_link", [options.rr, output, options.nbaccess, options.filterzone, options.filterdraw, removedZones]])

	if options.ins != 'not_filled':
		if options.prefix != 'not_filled':
			output = options.prefix+'_zone_ins.link'
		else:
			output = options.out_ins
		if options.removedZones:
			removedZones = pathToScoreFiles['ins']
		else:
			removedZones = 0
		listJobs.append(["create_discord_link", [options.ins, output, options.nbaccess, options.filterzone, options.filterdraw, removedZones]])

	if options.delet != 'not_filled':
		if options.prefix != 'not_filled':
			output = options.prefix+'_zone_delet.link'
		else:
			output = options.out_delet
		if options.removedZones:
			removedZones = pathToScoreFiles['delet']
		else:
			removedZones = 0
		listJobs.append(["create_discord_link", [options.delet, output, options.nbaccess, options.filterzone, options.filterdraw, removedZones]])

	if options.chr_rr != 'not_filled':
		if options.prefix != 'not_filled':
			output = options.prefix+'_zone_chr_rr.link'
		else:
			output = options.out_chr_rr
		if options.removedZones:
			removedZones = pathToScoreFiles['chr_rr']
		else:
			removedZones = 0
		listJobs.append(["create_discord_link", [options.chr_rr, output, options.nbaccess, options.filterzone, options.filterdraw, removedZones]])

	if options.chr_rf != 'not_filled':
		if options.prefix != 'not_filled':
			output = options.prefix+'_zone_chr_rf.link'
		else:
			output = options.out_chr_rf
		if options.removedZones:
			removedZones = pathToScoreFiles['chr_rf']
		else:
			removedZones = 0
		listJobs.append(["create_discord_link", [options.chr_rf, output, options.nbaccess, options.filterzone, options.filterdraw, removedZones]])

	if options.chr_ff != 'not_filled':
		if options.prefix != 'not_filled':
			output = options.prefix+'_zone_chr_ff.link'
		else:
			output = options.out_chr_ff
		if options.removedZones:
			removedZones = pathToScoreFiles['chr_ff']
		else:
			removedZones = 0
		listJobs.append(["create_discord_link", [options.chr_ff, output, options.nbaccess, options.filterzone, options.filterdraw, removedZones]])

	if options.chr_fr != 'not_filled':
		if options.prefix != 'not_filled':
			output = options.prefix+'_zone_chr_fr.link'
		else:
			output = options.out_chr_fr
		if options.removedZones:
			removedZones = pathToScoreFiles['chr_fr']
		else:
			removedZones = 0
		listJobs.append(["create_discord_link", [options.chr_fr, output, options.nbaccess, options.filterzone, options.filterdraw, removedZones]])


	#For read link
	if options.liste_read != 'not_filled':
		if options.orient == 'rf':
			if options.prefix != 'not_filled':
				output1 = options.prefix+'_read_rf.link'
				output2 = options.prefix+'_read_fr.link'
				flag1 = 'ok'
				flag2 = 'fr'
			else:
				output1 = options.Rout_rf
				output2 = options.Rout_fr
				flag1 = 'ok'
				flag2 = 'fr'
		elif options.orient == 'fr':
			if options.prefix != 'not_filled':
				output1 = options.prefix+'_read_rf.link'
				output2 = options.prefix+'_read_fr.link'
				flag1 = 'rf'
				flag2 = 'ok'
			else:
				output1 = options.Rout_rf
				output2 = options.Rout_fr
				flag1 = 'rf'
				flag2 = 'ok'
		else:
			mot = 'Unrecognized argument in --orient %s' % options.orient
			sys.exit(mot)

		listJobs.append(["create_read_link", [options.liste_read, output1, flag1]])
		listJobs.append(["create_read_link", [options.liste_read, output2, flag2]])

		if options.prefix != 'not_filled':
			listJobs.append(["create_read_link", [options.liste_read, options.prefix+'_read_ff.link', 'ff']])
			listJobs.append(["create_read_link", [options.liste_read, options.prefix+'_read_rr.link', 'rr']])
			listJobs.append(["create_read_link", [options.liste_read, options.prefix+'_read_ins.link', 'ins']])
			listJobs.append(["create_read_link", [options.liste_read, options.prefix+'_read_delet.link', 'del']])
			listJobs.append(["create_read_link", [options.liste_read, options.prefix+'_read_chr_rr.link', 'chr_rr']])
			listJobs.append(["create_read_link", [options.liste_read, options.prefix+'_read_chr_rf.link', 'chr_rf']])
			listJobs.append(["create_read_link", [options.liste_read, options.prefix+'_read_chr_ff.link', 'chr_ff']])
			listJobs.append(["create_read_link", [options.liste_read, options.prefix+'_read_chr_fr.link', 'chr_fr']])
		else:
			listJobs.append(["create_read_link", [options.liste_read, options.Rout_ff, 'ff']])
			listJobs.append(["create_read_link", [options.liste_read, options.Rout_rr, 'rr']])
			listJobs.append(["create_read_link", [options.liste_read, options.Rout_ins, 'ins']])
			listJobs.append(["create_read_link", [options.liste_read, options.Rout_delet, 'del']])
			listJobs.append(["create_read_link", [options.liste_read, options.Rout_chr_rr, 'chr_rr']])
			listJobs.append(["create_read_link", [options.liste_read, options.Rout_chr_rf, 'chr_rf']])
			listJobs.append(["create_read_link", [options.liste_read, options.Rout_chr_ff, 'chr_ff']])
			listJobs.append(["create_read_link", [options.liste_read, options.Rout_chr_fr, 'chr_fr']])

	if options.agp != 'not_filled':
		if options.prefix != 'not_filled':
			output = options.prefix+'_scaffold.tile'
		else:
			output = options.out_scaff
		listJobs.append(["create_tile", [options.agp, output]])

	pool = multiprocessing.Pool(processes=nbProcs)
	results = pool.map(worker, listJobs)

	print "Nb accession : "+options.nbaccess
	print "filterZone : "+options.filterzone
	print "filterDraw : "+options.filterdraw
	print "frf : "+options.frf
	print "ff : "+options.ff
	print "rr : "+options.rr
	print "ins : "+options.ins
	print "delet : "+options.delet
	print "chr_ff : "+options.chr_ff
	print "chr_fr : "+options.chr_fr
	print "chr_rf : "+options.chr_rf
	print "chr_rr : "+options.chr_rr
	print "total time : "+str(datetime.datetime.now() - t0)

	for job in results:
		if job[0]:
			errorValue = "Sorry the job \""+str(job[2])+" ( "+job[3][0]+", "+job[3][1]+", "+str(job[3][2])+", "+job[3][3]+" )\" hasn't been completed."
			sys.exit(errorValue)
		elif job[2] == "calcul_couv_moy":
			median_cov = job[1][0]
			mean_cov = job[1][1]

	config = ConfigParser.RawConfigParser()
	if options.prefix != 'not_filled':
		config.add_section('General')
		config.set('General','chr', os.path.abspath(options.chr))
		config.set('General','out_kar', os.path.abspath(options.prefix+'_karyotype.txt'))
		config.set('General','out_N', os.path.abspath(options.prefix+'_loc_N.txt'))
		config.set('General','out_housekeeping', os.path.abspath(options.prefix+'_housekeeping.conf'))
		config.set('General','orient', options.orient)
		if options.cov != 'not_filled':
			config.add_section('Coverage')
			config.set('Coverage','cov', os.path.abspath(options.prefix+'_mean.cov'))
			config.set('General','cov', 'yes')
			config.set('Coverage','median_cov', str(median_cov))
			config.set('Coverage','mean_cov', str(mean_cov))
		else:
			config.set('General','cov', 'no')
		config.add_section('Discord_link')
		config.add_section('Discord_zone')
		if options.frf != 'not_filled':
			config.set('Discord_link','frf', os.path.abspath(options.prefix+'_zone_frf.link'))
			config.set('General','frf', 'yes')
		else:
			config.set('General','frf', 'no')

		if options.ff != 'not_filled':
			config.set('Discord_link','ff', os.path.abspath(options.prefix+'_zone_ff.link'))
			config.set('General','ff', 'yes')
		else:
			config.set('General','ff', 'no')

		if options.rr != 'not_filled':
			config.set('Discord_link','rr', os.path.abspath(options.prefix+'_zone_rr.link'))
			config.set('General','rr', 'yes')
		else:
			config.set('General','rr', 'no')

		if options.ins != 'not_filled':
			config.set('Discord_link','ins', os.path.abspath(options.prefix+'_zone_ins.link'))
			config.set('General','ins', 'yes')
		else:
			config.set('General','ins', 'no')

		if options.delet != 'not_filled':
			config.set('Discord_link','delet', os.path.abspath(options.prefix+'_zone_delet.link'))
			config.set('General','delet', 'yes')
		else:
			config.set('General','delet', 'no')

		if options.chr_rr != 'not_filled':
			config.set('Discord_link','chr_rr', os.path.abspath(options.prefix+'_zone_chr_rr.link'))
			config.set('Discord_zone','chr_rr', os.path.abspath(options.chr_rr))
			config.set('General','chr_rr', 'yes')
		else:
			config.set('General','chr_rr', 'no')

		if options.chr_rf != 'not_filled':
			config.set('Discord_link','chr_rf', os.path.abspath(options.prefix+'_zone_chr_rf.link'))
			config.set('Discord_zone','chr_rf', os.path.abspath(options.chr_rf))
			config.set('General','chr_rf', 'yes')
		else:
			config.set('General','chr_rf', 'no')

		if options.chr_fr != 'not_filled':
			config.set('Discord_link','chr_fr', os.path.abspath(options.prefix+'_zone_chr_fr.link'))
			config.set('Discord_zone','chr_fr', os.path.abspath(options.chr_fr))
			config.set('General','chr_fr', 'yes')
		else:
			config.set('General','chr_fr', 'no')

		if options.chr_ff != 'not_filled':
			config.set('Discord_link','chr_ff', os.path.abspath(options.prefix+'_zone_chr_ff.link'))
			config.set('Discord_zone','chr_ff', os.path.abspath(options.chr_ff))
			config.set('General','chr_ff', 'yes')
		else:
			config.set('General','chr_ff', 'no')

		if options.liste_read != 'not_filled':
			config.add_section('Read_link')
			config.set('Read_link','rf', os.path.abspath(options.prefix+'_read_rf.link'))
			config.set('Read_link','fr', os.path.abspath(options.prefix+'_read_fr.link'))
			config.set('Read_link','ff', os.path.abspath(options.prefix+'_read_ff.link'))
			config.set('Read_link','rr', os.path.abspath(options.prefix+'_read_rr.link'))
			config.set('Read_link','ins', os.path.abspath(options.prefix+'_read_ins.link'))
			config.set('Read_link','del', os.path.abspath(options.prefix+'_read_delet.link'))
			config.set('Read_link','chr_rr', os.path.abspath(options.prefix+'_read_chr_rr.link'))
			config.set('Read_link','chr_rf', os.path.abspath(options.prefix+'_read_chr_rf.link'))
			config.set('Read_link','chr_fr', os.path.abspath(options.prefix+'_read_chr_fr.link'))
			config.set('Read_link','chr_ff', os.path.abspath(options.prefix+'_read_chr_ff.link'))
			config.set('General','read_rf', 'yes')
			config.set('General','read_fr', 'yes')
			config.set('General','read_ff', 'yes')
			config.set('General','read_rr', 'yes')
			config.set('General','read_ins', 'yes')
			config.set('General','read_del', 'yes')
			config.set('General','read_chr_rr', 'yes')
			config.set('General','read_chr_rf', 'yes')
			config.set('General','read_chr_fr', 'yes')
			config.set('General','read_chr_ff', 'yes')
		else:
			config.set('General','read_rf', 'no')
			config.set('General','read_fr', 'no')
			config.set('General','read_ff', 'no')
			config.set('General','read_rr', 'no')
			config.set('General','read_ins', 'no')
			config.set('General','read_del', 'no')
			config.set('General','read_chr_rr', 'no')
			config.set('General','read_chr_rf', 'no')
			config.set('General','read_chr_fr', 'no')
			config.set('General','read_chr_ff', 'no')

		if options.dis_prop != 'not_filled':
			config.add_section('Proportion')
			config.set('Proportion','prop', os.path.abspath(options.dis_prop))
			config.set('General','prop', 'yes')
		else:
			config.set('General','prop', 'no')

		if options.agp != 'not_filled':
			config.add_section('Scaffold')
			config.set('Scaffold','scaff_tile', os.path.abspath(options.prefix+'_scaffold.tile'))
			config.set('General','scaff_tile', 'yes')
		else:
			config.set('General','scaff_tile', 'no')
		# writting configuration file
		with open(options.prefix+'.conf', 'wb') as configfile:
			config.write(configfile)
	else:
		config.add_section('General')
		config.set('General','chr', os.path.abspath(options.chr))
		config.set('General','out_kar', os.path.abspath(options.out_kar))
		config.set('General','out_N', os.path.abspath(options.out_N))
		config.set('General','orient', options.orient)
		if options.cov != 'not_filled':
			config.add_section('Coverage')
			config.set('Coverage','cov', os.path.abspath(options.out_cov))
			config.set('General','cov', 'yes')
			config.set('Coverage','median_cov', str(median_cov))
			config.set('Coverage','mean_cov', str(mean_cov))
		else:
			config.set('General','cov', 'no')
		config.add_section('Discord_link')
		config.add_section('Discord_zone')
		if options.frf != 'not_filled':
			config.set('Discord_link','frf', os.path.abspath(options.out_frf))
			config.set('General','frf', 'yes')
		else:
			config.set('General','frf', 'no')

		if options.ff != 'not_filled':
			config.set('Discord_link','ff', os.path.abspath(options.out_ff))
			config.set('General','ff', 'yes')
		else:
			config.set('General','ff', 'no')

		if options.rr != 'not_filled':
			config.set('Discord_link','rr', os.path.abspath(options.out_rr))
			config.set('General','rr', 'yes')
		else:
			config.set('General','rr', 'no')

		if options.ins != 'not_filled':
			config.set('Discord_link','ins', os.path.abspath(options.out_ins))
			config.set('General','ins', 'yes')
		else:
			config.set('General','ins', 'no')

		if options.delet != 'not_filled':
			config.set('Discord_link','delet', os.path.abspath(options.out_delet))
			config.set('General','delet', 'yes')
		else:
			config.set('General','delet', 'no')

		if options.chr_rr != 'not_filled':
			config.set('Discord_link','chr_rr', os.path.abspath(options.out_chr_rr))
			config.set('Discord_zone','chr_rr', os.path.abspath(options.chr_rr))
			config.set('General','chr_rr', 'yes')
		else:
			config.set('General','chr_rr', 'no')

		if options.chr_rf != 'not_filled':
			config.set('Discord_link','chr_rf', os.path.abspath(options.out_chr_rf))
			config.set('Discord_zone','chr_rf', os.path.abspath(options.chr_rf))
			config.set('General','chr_rf', 'yes')
		else:
			config.set('General','chr_rf', 'no')

		if options.chr_fr != 'not_filled':
			config.set('Discord_link','chr_fr', os.path.abspath(options.out_chr_fr))
			config.set('Discord_zone','chr_fr', os.path.abspath(options.chr_fr))
			config.set('General','chr_fr', 'yes')
		else:
			config.set('General','chr_fr', 'no')

		if options.chr_ff != 'not_filled':
			config.set('Discord_link','chr_ff', os.path.abspath(options.out_chr_ff))
			config.set('Discord_zone','chr_ff', os.path.abspath(options.chr_ff))
			config.set('General','chr_ff', 'yes')
		else:
			config.set('General','chr_ff', 'no')

		if options.liste_read != 'not_filled':
			config.add_section('Read_link')
			config.set('Read_link','rf', os.path.abspath(options.Rout_rf))
			config.set('Read_link','fr', os.path.abspath(options.Rout_fr))
			config.set('Read_link','ff', os.path.abspath(options.Rout_ff))
			config.set('Read_link','rr', os.path.abspath(options.Rout_rr))
			config.set('Read_link','ins', os.path.abspath(options.Rout_ins))
			config.set('Read_link','del', os.path.abspath(options.Rout_delet))
			config.set('Read_link','chr_rr', os.path.abspath(options.Rout_chr_rr))
			config.set('Read_link','chr_rf', os.path.abspath(options.Rout_chr_rf))
			config.set('Read_link','chr_fr', os.path.abspath(options.Rout_chr_fr))
			config.set('Read_link','chr_ff', os.path.abspath(options.Rout_chr_ff))
			config.set('General','read_rf', 'yes')
			config.set('General','read_fr', 'yes')
			config.set('General','read_ff', 'yes')
			config.set('General','read_rr', 'yes')
			config.set('General','read_ins', 'yes')
			config.set('General','read_del', 'yes')
			config.set('General','read_chr_rr', 'yes')
			config.set('General','read_chr_rf', 'yes')
			config.set('General','read_chr_fr', 'yes')
			config.set('General','read_chr_ff', 'yes')
		else:
			config.set('General','read_rf', 'no')
			config.set('General','read_fr', 'no')
			config.set('General','read_ff', 'no')
			config.set('General','read_rr', 'no')
			config.set('General','read_ins', 'no')
			config.set('General','read_del', 'no')
			config.set('General','read_chr_rr', 'no')
			config.set('General','read_chr_rf', 'no')
			config.set('General','read_chr_fr', 'no')
			config.set('General','read_chr_ff', 'no')

		if options.dis_prop != 'not_filled':
			config.add_section('Proportion')
			config.set('Proportion','prop', os.path.abspath(options.dis_prop))
			config.set('General','prop', 'yes')
		else:
			config.set('General','prop', 'no')

		if options.agp != 'not_filled':
			config.add_section('Scaffold')
			config.set('Scaffold','scaff_tile', os.path.abspath(options.out_scaff))
			config.set('General','scaff_tile', 'yes')
		else:
			config.set('General','scaff_tile', 'no')
		# writting configuration file
		with open(options.output, 'wb') as configfile:
			config.write(configfile)

if __name__ == "__main__": __main__()
