#!/usr/bin/python2

###############################
# Distributed encoding client #
###############################

import os
import os.path
import socket
import struct
import sys
import threading
import time

if sys.platform.startswith('linux'):
	X264 = "ffmpeg"
elif sys.platform.startswith('win32') or sys.platform.startswith('cygwin'):
	X264 = "x264.exe"
else:
	print "Your platform %s is not supported." % sys.platform
PORT = 13337
UPLOAD = False
NETWORK_CHUNK = 4096
DEBUG = 5
VERSION = "0.2"

print "Distributed encoding client version %s running on %s." % (VERSION, sys.platform)

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

# misc. functions

def getCRC(string):
	CRCs = re.findall("\[[0-F]{8}\]", string)
	if len(CRCs) == 0:
		return 0
	return CRCs[0].strip("][")

def info(string):
	if DEBUG > 4:
		print "(II)", string

def warn(string):
	if DEBUG > 2:
		print "(WW)", string

def error(string):
	if DEBUG > 0:
		print "(EE)", string

def usage():
	print "Stub print usage here, lol"

# socket functions

def get(sock, size):
	info("Retrieving " + str(size) + " bytes.")
	ret = ""
	chunk = NETWORK_CHUNK
	while size != 0:
		if size < chunk:
			chunk = size
		temp = sock.recv(chunk)
		size -= len(temp)
		ret += temp
	return ret

def get_into(sock, fd, size):
	info("Retrieving " + str(size) + " bytes and writing to file.")
	chunk = NETWORK_CHUNK
	bytes = size
	start = time.time()
	while size != 0:
		if size < chunk:
			chunk = size
		temp = sock.recv(chunk)
		size -= len(temp)
		fd.write(temp)
	end = time.time()
	if end - start > 0:
		bitrate = (bytes / 1024) / (end - start)
	else:
		bitrate = 9001
	info("Retrieved %d in %ds. (%d kB/s)" % (bytes, int(end - start), bitrate))
	
def get_line(sock):
	info("Retrieving line from socket.")
	line = ""
	char = sock.recv(1)
	while char != '\n':
		line += char
		char = sock.recv(1)
	return line

def send_file(sock, filename):
	size = os.path.getsize(filename)
	info("Sending file %s of size %d" % (filename, size))
	fd = open(filename, "r")
	start = time.time()
	sock.send(struct.pack("!i", size))
	sock.sendall(fd.read())
	end = time.time()
	if end - start > 0:
		bitrate = (size / 1024) / (end - start)
	else:
		bitrate = 9001
	info("Sent %d in %ds. (%d kB/s)" % (size, int(end - start), bitrate))

class FileSender(threading.Thread):
	def __init__(self, sock, filename):
		threading.Thread.__init__(self)
		self.sock = sock
		self.filename = filename
	def run(self):
		self.sock.send("RDY")
		self.sock.send("[8bit] " + self.filename + '\n')
		send_file(self.sock, "[8bit] " + self.filename)
		self.sock.close()
# client specific functions

def add(sock, filename, encode):
	server.send("ADD")
	server.send(filename + '\n')
	ret = get(sock, 1)
	if ret == "D":
		info("Duplicate not added.")
		exit(0)
	elif ret == "Y":
		info("Adding new file...")
	elif ret == "N":
		info("File has not been found.")
		if UPLOAD:
			sock.send("Y")
			info("Sending file...")
			send_file(sock, filename)
		else:
			sock.send("N")
			info("Not sending file, terminating")
			exit(0)
	info("Sending encode settings.")
	sock.send(encode + '\n')
	if get(sock, 1) == "S":
		info("Success!")
	else:
		error("Unkown error!")
	sock.close()

def encode(sock):
	address = sock.getpeername()
	sock.send("LGN")
	ret = get(sock, 1)
	if ret == "N":
		sock.close()
		info("Nothing to encode.")
		exit(0)
	elif ret == "Y":
		filename = get_line(sock)
		(size,) = struct.unpack("!i", get(sock, 4))
		download = open(filename, "w")
		get_into(sock, download, size)
		encode = get_line(sock)
		sock.close()
		#x264_execute = X264 + " %s -o \"[8bit] %s\" \"%s\"" % (encode, filename, filename)
		x264_execute = X264 + " -i %s %s \"[8bit] %s\"" % (filename, encode, filename)
		info("Executing %s" % x264_execute)
		#placebo = "mv %s [8bit]\ %s" % (filename, filename)
		os.system(x264_execute)
		print address
		sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		sock.connect(address)
		sender = FileSender(sock, filename)
		sender.start()
		os.remove(filename)

def log_on(sock, host, n):
	if n == 0:
		while True:
			sock.connect((host, PORT))
			encode(sock)
			sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
	else:
		for i in range(n):
			sock.connect((host, PORT))
			encode(sock)
			sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

def main():
	print sys.argv
	if len(sys.argv) < 3:
		usage()
		exit(1)
	if sys.argv[2] == "ADD":
		if len(sys.argv) < 5:
			usage()
			exit(1)
		server.connect((sys.argv[1], PORT))
		add(server, sys.argv[3], sys.argv[4])
		exit(0)
	if sys.argv[2] == "LGN":
		if len(sys.argv) < 4:
			log_on(server, sys.argv[1], 0)
		else:
			log_on(server, sys.argv[1], int(sys.argv[3]))
		exit(0)
	usage()
	exit(1)
main()
