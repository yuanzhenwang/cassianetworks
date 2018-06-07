# from urllib2 import Request, urlopen
import requests
import base64
import json
import threading
import os
import time
import socket
import paramiko
import csv


scanning_aps = []
headers = {}
scan_data_count = 0
counts = 0
SSE_CLIENT = {}
active = None
# test_time = 0
ac_root_pwd = ''
data_path = ''
TESTING = True
speed = 0
# scanning_aps = 0
global MONITOR,ssh_client,sftp_client,copy_timer

#SSH登录AC，执行性能监控任务
def start_ac_monitor(test_time):
	#开始新的监控进程，生成全新的测试文件
	if test_time>7200:
		interval = '30'
		count = str(int(test_time)/int(interval))
	else:
		interval = '3'
		count = str(int(test_time)/int(interval))
	cmd1 = '/tmp/nmon_x86_centos6 -f -N -m /tmp/res/ -s '+ interval +' -c '+count
	cmd2 = 'top -d '+interval+' -n '+count+' -b >>/tmp/res/monitor_data_top.txt 2>&1 &'
	cmd3 = 'pidstat -r '+interval+' '+count+' >>/tmp/res/monitor_data_mem.txt 2>&1 &'
	cmd4 = 'pidstat -d '+interval+' '+count+' >>/tmp/res/monitor_data_disk.txt 2>&1 &'
	try:
		if run_mode == '0':
			ssh_client.exec_command(cmd2)
			ssh_client.exec_command(cmd3)
			ssh_client.exec_command(cmd4)
		elif run_mode == '1':
			ssh_client.exec_command(cmd1)
			ssh_client.exec_command(cmd2)
		print('成功开启AC性能监控，数据文件保存在%s:/tmp/res/\n'%ip)
	except Exception as e:
		print('AC性能监控开启失败，\n',e)

#从AC拷贝数据文件
def copy_file(flag = True):
	global data_path,copy_timer
	no = 0
	src = '/tmp/res/'
	print('开始从服务器拷贝文件到本地\n')
	try:
		files = sftp_client.listdir('/tmp/res/')
		for file in files:
			sftp_client.get(src+file,data_path+file)
		print('成功从AC拷贝测试结果文件到目录%s\n'%data_path)	
	except Exception as e:
		#只有在结束测试时，拷贝失败尝试重新拷贝,默认为不重试
		if flag:
			pass
		else:
			while no < 3:
				try:
					print('从服务器copy文件失败,正在重试\n')
					files = sftp_client.listdir('/tmp/res/')
					for file in files:
						sftp_client.get(src+file,data_path+file)
				except:
					pass
				no += 1
			print('从服务器copy文件失败，请手动copy\n',e)
			return

	write_csv()	

	'''通过标志位判断是否继续调用自身，当停止测试最后一次调用时，flag应该为false,
		否则程序不能自动结束运行。
	'''
	if flag:
		copy_timer = threading.Timer(1800,copy_file,)
		copy_timer.start()
	else:
		pass

#提取测试数据，并写入到data_path目录下的data.csv文件中 
def write_csv():
	for file in os.listdir(data_path):
		filename = file.split('.')[0]
		if filename == 'monitor_data_top':
			with open(data_path+file,'r',encoding = 'utf-8') as f:
				nfm_rows =[['name','CPU','MEM']]
				ac_rows =[['name','CPU','MEM']]
				mongod_rows = [['name','CPU','MEM']]
				node_rows =[['name','CPU','MEM']]
				cpu_total_rows = [['name','us','sy','id','wa','si']]
				mem_total_rows = [['name','free','used','total','buff']]
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
							name,cpu,mem = data[11]+'_'+data[0],data[8],data[9]
							node_rows.append([name,cpu,mem])
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
							mem_total_rows.append(['MEM_total',int(int(data[5][:-1])/1024),
													int(int(data[3][:-1])/1024),int(int(data[1][:-1])/1024),
													int(int(data[7][:-1])/1024)])
						else:
							pass
					except:
						pass
				# print(min(len(nfm_rows),len(ac_rows),len(mongod_rows)))
			with open(data_path+'monitor_data_top.csv','w',newline='') as f:
				csv_write = csv.writer(f,dialect='excel')
				min_len = min(len(ac_rows),len(nfm_rows),len(mongod_rows),len(mem_total_rows),len(cpu_total_rows))
				for i in range(min_len):
					L = ac_rows[i]+nfm_rows[i]+mongod_rows[i]+mem_total_rows[i]+cpu_total_rows[i]+node_rows[i]
					csv_write.writerow(L)

#读取配置文件
def init_config():
	global HOST,user,pwd,active,server,INTERVAL,PER_COUNT,test_time,ac_root_pwd,data_path,run_mode,active
	try:
		with open('test.conf','r',encoding = 'utf-8') as conf:
			for line in conf:
				line = line.strip()
				if line:
					if line.startswith('#'):
						pass
					else:
						# print('line:',ascii(line[0]))
						key =line.split('=')[0].strip()
						value =line.split('=')[1].strip()
						if key == 'HOST':
							HOST = value
						elif key == 'user':
							user = value
						elif key =='pwd':
							pwd = value
						elif key =='active':
							active = value
						elif key == 'server':
							server = value
						elif key =='test_time':
							test_time = int(value)
						elif key == 'ac_root_pwd':
							ac_root_pwd = value
						elif key =='data_path':
							data_path = value
						elif key == 'run_mode':
							run_mode = value
						elif key == 'avtive':
							active = value
			print('配置文件读取成功！\n')
	except Exception as e:
		print('配置文件打开失败,失败原因:\n',e)

def init_monitor_client():
	global sftp_client,ssh_client
	ip = HOST.split('/')[2]
	try:
		#初始化sftp客户端
		# noinspection PyTypeChecker
		ftp = paramiko.Transport((ip,22))
		ftp.connect(username='root',password= ac_root_pwd)
		sftp_client = paramiko.SFTPClient.from_transport(ftp)
		#初始化ssh客户端
		ssh_client = paramiko.SSHClient()
		ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
		ssh_client.connect(ip,22,'root',ac_root_pwd,timeout=5)
		print('Monitor client init successed!\n')
	except:
		print('Monitor client init failed!\n')
	try:
		ssh_client.exec_command('killall top')
		ssh_client.exec_command('killall pidstat')
		ssh_client.exec_command('killall nmon_x86_centos6')
	except:
		pass
	src = '/tmp/res/'
	try:
		history_files = sftp_client.listdir(src)
	except:
		sftp_client.mkdir(src)
		history_files = sftp_client.listdir(src)
	if len(history_files)>0:
		print('删除历史遗留数据文件!\n')
		for file in history_files:
			sftp_client.remove(src+file)

#客户端，负责与服务器的连接，并且接收从服务器发来的数据
def connect_to_server(server):
	global sock
	sock = socket.socket()
	sock.connect((server,8080))
	sock.send(bytes('config_req',encoding = 'utf-8'))
	while True:
		if TESTING:
			try:
				data = sock.recv(10240)
			except Exception as e:
				print(e)
			message = str(data,encoding = 'utf-8')
			data_type = message.split('+')[0].strip()
			# print(data_type,message)
			send_para(sock,message,data_type)
		else:
			break

#数据处理函数，负责解析从服务器接受到的参数以及向服务器发送数据
def send_para(sock,data,data_type):
	#定义全局测试参数
	global PC_COUNT,PC_NO,START_TIME,INTERVAL,PER_COUNT,HUBS,sessionID,scanning_aps,user,pwd,HOST,run_mode
	if data_type == 'config_res':
		sock.send(bytes('config_ok',encoding = 'utf-8'))
		#解析并设置从服务器获取的全局测试参数
		START_TIME = int(data.split('+')[1])
		INTERVAL = int(data.split('+')[2])
		PER_COUNT = int(data.split('+')[3])
		HUBS = data.split('+')[4].split(",")
		user = data.split('+')[5]
		pwd = data.split('+')[6]
		HOST = data.split('+')[7]
		run_mode = data.split("+")[8]
		# print(START_TIME,PER_COUNT,INTERVAL,HUBS)
		print('######################################################')
		print("     成功从控制器获取测试数据，等待测试开始！")
		print('######################################################')
	elif data_type == 'test_start':
		start_test()
	elif data_type == 'session':
		sessionID = int(data.split('+')[1].strip())
	elif data_type == 'bak_ap_scan':
		delmac = data.split('+')[2].strip()
		scanning_aps.remove(delmac)
		mac = data.split('+')[1].strip()
		threading.Thread(target = scan,args =(sock,mac,True,)).start()
	elif data_type == 'test_stop':
		stop_test(sock)

#开始AP扫描
def scan(sock,mac,bak=False):
	# print('thread %s is running...' % threading.current_thread().name)
	global scanning_aps,scan_data_count,sockt,HOST,headers
	flag = True
	try:
		data = {"event":1,'mac':mac}
		# print(data)
		res = requests.get(HOST + '/gap/nodes',params = data,headers = headers,stream =True)
			# file_name = 'res_of_'+ re.sub('[^0-9A-F]','',mac) +'.txt'
		for line in res.iter_lines():
			# filter out keep-alive new lines
			s = str(line,encoding = 'utf-8')
			# print(s)
			if s.startswith('data'):
				#检查是否为第一条扫描数据，是第一条的话就将开启扫描的AP数量+1；该条件语句只会执行一次				
				if flag ==True:
					#检查是否为备用AP开启扫描
					if bak:
						print("Bak ap %s start scan success!"%mac)
						scanning_aps.append(mac)
						SSE_CLIENT[mac] = res
						#向server响应备用AP扫描是否开启成功
						sock.send(bytes('bak_ap_scan+'+mac,encoding='utf-8'))
						print('当前扫描的AP总数为：%s\n\n'%len(scanning_aps),end = '')
						flag = False
						scan_data_count = scan_data_count +1
					else:
						print("AP %s start scan success!"%mac)
						scanning_aps.append(mac)
						SSE_CLIENT[mac] = res
						print('当前扫描的AP总数为：%s\n\n'%len(scanning_aps),end = '')
						flag = False
						scan_data_count = scan_data_count +1
				else:
					scan_data_count = scan_data_count +1
					# print(s)
					# print(' AP %s scan count is %d \r'%(mac,count),end ='')
					# with open('./scan_result/'+file_name,'a') as f:
					# 	f.write(str(count)+'\n')
	except Exception as e:
			if str(e) =="'NoneType' object has no attribute 'read'":
				pass
			else:
				print('SSE closeed!',threading.current_thread().name,e)
			# scan(sock,mac)

def sync_to_server():
	global scanning_aps
	while True:
		if TESTING:
			sock.send(bytes('sync+'+str(sessionID)+'+'+str(speed)+'+'+str(len(scanning_aps)),encoding = 'utf-8'))
			time.sleep(10)
		else:
			break

#获取所有在线AP
def get_online_hubs():
	res = requests.get(HOST + '/cassia/hubs',headers = headers)
	res_hub_info = json.loads(res.text)
	hubs = []
	for i in res_hub_info:
		hubs.append(i['mac'])
	# print(type(hubs),hubs)
	return hubs
	
#计算AP的sap秒速度，该速度为平均值	
def scan_speed():
	global scan_data_count,scanning_aps,counts,speed_timer,speed
	per_time = 10
	if len(scanning_aps)>0:
		speed = int((scan_data_count - counts)/(per_time*len(scanning_aps)))
	else:
		print('WARNING:NO AP SCANNING NOW!!!\n')
		speed_timer = threading.Timer(per_time,scan_speed).start()
		return
	print('当前平均每台AP的扫描速度为:%d\n'%speed)
	date = time.strftime('%m-%d:%H:%M:%S',time.localtime())
	with open('speed.txt','a') as f:
		f.write(date +'--'+str(speed)+'\n')
	counts = scan_data_count
	speed_timer = threading.Timer(per_time,scan_speed)
	speed_timer.start()

#设置请求头
def set_header(user,pwd):
	global headers,sethead_timer,HOST
	use_info = user+':'+pwd
	#编码开发者帐号
	encode_info =base64.b64encode(use_info.encode('utf-8'))
	head = {
		'Content-Type': 'application/json',
		'Authorization': 'Basic '+ encode_info.decode("utf-8")
	}
	data = {'grant_type':'client_credentials'}
	try:
		#发起请求
		res = requests.post(HOST + '/oauth2/token', data= json.dumps(data),headers = head)
		# print(res.text,res.status_code)
		if res.status_code == 200:
			res_body = json.loads(res.text)
			# print(res_body.get("access_token"))
			TOKEN = res_body.get("access_token")
		elif res.status_code == 401:
			print('开发帐号错误')
		elif res.status_code == 400:
			print('API路径错误')
	except Exception as e:
		print(e)
	headers = {
	  'Content-Type': 'application/json',
	  'version': '1',
	  'Authorization':'Bearer ' + TOKEN
	}
	# print(headers)
	# noinspection PyTypeChecker
	sethead_timer = threading.Timer(3500,set_header,(user,pwd))
	sethead_timer.start()

#一次性开启所有在线AP扫描
def all_ap_scan(sock,hubs):
	print('AP总数量为%d，开始扫描！\n'%len(hubs))
	threads = []
	for hub in hubs:
		# print(hub)
		threads.append(threading.Thread(target = scan,args =(sock,hub,)))
	# print(len(threads),threads)
	for t in threads:
		t.start()
	# t.join(30)

#逐渐开启AP扫描
def scan_by_interval(hubs,interval,per_count,start_time=0):
	i = 0
	j = per_count
	time.sleep(start_time)
	print('AP总数量为%d，开始扫描！\n'%len(hubs))
	while True:
		if i <j:
			threading.Thread(target = scan,args =(sock,hubs[i],)).start()
			i = i + 1			
		else:
			j = j + per_count
			if j >len(hubs):
				while j<len(hubs)-1:
					threading.Thread(target = scan,args =(sock,hubs[i],)).start()
					j = j + 1
				break
			time.sleep(interval)
	# t.join(10)

def start_test():
	if run_mode =='0':
		print('开始稳定性测试。。。\n')
		all_ap_scan(sock,HUBS)
		threading.Timer(10,scan_speed).start()
		time.sleep(10)
		threading.Thread(target = sync_to_server).start()
	elif run_mode =='1':
		print('开始性能测试。。。\n')
		if START_TIME>0:
			print('Other pc already started test,Waiting %d seconds to start test...'%START_TIME)
		threading.Thread(target = scan_by_interval,args = (HUBS,INTERVAL,PER_COUNT,START_TIME,)).start()
		threading.Timer(10,scan_speed).start()
		threading.Thread(target = sync_to_server).start()

def stop_test(sock):
	global TESTING
	TESTING = False
	ip = HOST.split('/')[2]
	try:
		sock.close()
		# MONITOR.close()
		# print('Stop ap monitor thread!\n')
		speed_timer.cancel()
		print('Stop ap scan speed monitor thread!\n')
		# copy_timer.cancel()
		# print('Stop data copy thread!\n')
		sethead_timer.cancel()
		print('Stop token update thread!\n')
	except Exception as e:
		print(e)
	print('Stopping ap scan...\n')
	for key, value in SSE_CLIENT.items():
		value.close()
		# print("ap %s stop scan!"%key)
	print('All ap have stoped scan!\n\nTest finished!\n')

#监控AP上下线
def hub_status():
	global SSE_CLIENT,MONITOR,scaning_aps
	try:
		MONITOR = requests.get(HOST + '/cassia/hubStatus',headers = headers,stream =True)
		for line in MONITOR.iter_lines():
			message = str(line,encoding='utf-8')
			if message.startswith('data'):
				message = json.loads(message[6:])
				# print(message['mac'])
				# print(message['status'])
				if message['status']=='online':
					print('AP %s 上线，尝试开启扫描...'%message['mac'])
					threading.Thread(target = scan,args = (None,message['mac'],False)).start()
				elif message['status']=='offline':
					print('AP %s 离线，正在停止扫描...'%message['mac'])
					SSE_CLIENT.get(message['mac']).close()
					SSE_CLIENT.pop(message['mac'])
					scaning_aps.remove(message['mac'])
					print('当前扫描的AP总数为：%s\n\n'%len(scaning_aps),end = '')
			else:
				pass
	except Exception as e:
		print('Stop monitor ap.')			

def main():
	global headers,speed_timer,run_mode
	init_config()
	set_header(user,pwd)
	# init_monitor_client()
	# start_ac_monitor(test_time)
	# set_header(user,pwd)
	print(active)
	if active == 'True':
		hubs = get_online_hubs()
		threading.Timer(10,scan_speed).start()
		# copy_timer = threading.Timer(1800,copy_file)
		# copy_timer.start()
		# init_monitor_client()
		# start_ac_monitor(test_time)
		threading.Timer(test_time,stop_test).start()
		if run_mode =='0':
			print('开始稳定性测试。。。\n')
			threading.Thread(target = hub_status,args =()).start()
			all_ap_scan(None,hubs)
		elif run_mode =='1':
			print('开始性能测试。。。\n')
			scan_by_interval(hubs,INTERVAL,PER_COUNT)
	elif active == "False":
		threading.Thread(target = connect_to_server,args =(server,)).start()
	else:
		print('params active set error!')

if __name__ == '__main__':
	
	main()