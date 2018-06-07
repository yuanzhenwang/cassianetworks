import csv
import os,time
import asyncio

def write_csv():
	for files in os.listdir():
		name = files.split('.')[0]
		# print(name)
	with open('top.txt','r',encoding = 'utf-8') as f:
		nfm_rows =[['name','CPU','MEM']]
		ac_rows =[['name','CPU','MEM']]
		mongod_rows = [['name','CPU','MEM']]
		node_rows =[['name','CPU','MEM']]
		cpu_total_rows = [['name','us','sy','id','wa','si']]
		mem_total_rows = [['name','free','used','total','buff']]
		nodes = {}
		for line in f:
			# print(line)
			try:
				if 'NFM' in line:	
					data = line.split()
					name,cpu,mem = data[11],data[8],data[9]
					nfm_rows.append([name,cpu,mem])
				elif 'node' in line:
					# print(line)		
					data = line.split()
					if data[0] in nodes:
						name,cpu,mem = data[11]+'_'+data[0],data[8],data[9]
						nodes.get(data[0]).append([name,cpu,mem])
					else:
						nodes[data[0]]=[['name','CPU','MEM']]
						name,cpu,mem = data[11]+'_'+data[0],data[8],data[9]
						nodes.get(data[0]).append([name,cpu,mem])
					# name,cpu,mem = data[11]+'_'+data[0],data[8],data[9]
					# node_rows.append([name,cpu,mem])
				elif 'AC' in line:
					# print(line)
					data = line.split()
					name,cpu,mem = data[11],data[8],data[9]
					ac_rows.append([name,cpu,mem])
				elif 'mongod' in line:
					data = line.split()
					name,cpu,mem = data[11],data[8],data[9]
					mongod_rows.append([name,cpu,mem])
				elif line.startswith('Cpu'):
					data = line.split()
					cpu_total_rows.append(['CPU_total',data[1].split('%')[0],data[2].split('%')[0],
										   data[4].split('%')[0],data[5].split('%')[0],
										   data[7].split('%')[0]])
				elif line.startswith('Mem'):
					data = line.split()
					mem_total_rows.append(['MEM_total',int(int(data[5][:-1])/1024),int(int(data[3][:-1])/1024),
										   int(int(data[1][:-1])/1024),int(int(data[7][:-1])/1024)])
			except:
				pass
		print(mem_total_rows)
		# print(min(len(nfm_rows),len(ac_rows),len(mongod_rows)))
	with open('top.csv','w',newline='') as f:
		csv_write = csv.writer(f,dialect='excel')
		min_len = min(len(ac_rows),len(nfm_rows),len(mongod_rows),len(mem_total_rows),len(cpu_total_rows))
		# min_len = min(len(ac_rows),len(node_rows))
		for i in range(min_len):
			row = []
			node = [x[i] for _,x in nodes.items()]
			for x in node:
				for y in x:
					row.append(y)
			L = ac_rows[i]+nfm_rows[i]+mongod_rows[i]+mem_total_rows[i]+cpu_total_rows[i]+row
			# L = ac_rows[i]+node_rows[i]
			csv_write.writerow(L)
write_csv()
