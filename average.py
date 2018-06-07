from array import array
from collections import deque
import threading
import time
with open('data.txt','r') as f:
	data = [float(line.strip()) for line in f.readlines()]
i = 0
j = 20
for i in range(30):
	start = j*i
	end = j*(i+1)
	if end <len(data):
		s = data[start:end]
		s.sort()
		for k in range(4):
			s.pop(0)
			s.pop()
		print('%.2f'%(sum(s)/len(s)))
	else:
		pass

