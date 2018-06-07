import requests
import base64
import json
import threading
import re
import time
import socket
import sys,os
import paramiko,csv


CLIENTS = []
client_configs = []
hubs = 0
# SCANNING_APS = []	#二维数组，春初每个client当前的扫描AP数量
BAK_APS = []
OFFLINE_APS = 0
CLIENT_INFO = []
TESTING = True
config = {}

def init_config():
	global config
	try:
		with open('test.conf','r',encoding = 'utf-8') as conf:
			for line in conf:
				line = line.strip()
				if line:
					if line.startswith('#'):
						pass
					else:
						key =line.split('=')[0].strip()
						value =line.split('=')[1].strip()
						if key == 'HOST':
							config['host'] = value
						elif key == 'user':
							config['user'] = value
						elif key =='pwd':
							config['pwd'] = value
						elif key =='PROCESS_COUNT':
							config['process_count'] = int(value)
							config['process_no'] = 0
						elif key == 'INTERVAL':
							config['interval'] =int(value)
						elif key == 'PER_COUNT':
							config['per_count'] = int(value)
						elif key =='test_time':
							config['test_time'] = int(value)
						elif key =='MAX_OFFLINE':
							config['max_offline'] = int(value)
						elif key == 'test_mode':
							config['test_mode'] = value
						elif key == 'ac_root_pwd':
							config['ac_root_pwd'] = value	
						elif key =='data_path':
							config['data_path'] = value						
						else:
							pass
	except Exception as e:
		print('配置文件打开失败',e)

def init_para():
	global client_configs,hubs,BAK_APS
	i =0
	client_cfg = {}
	PROCESS_COUNT = config['process_count']
	set_header()
	hubs = get_online_hubs(headers)
	while i<config['max_offline']:
		BAK_APS.append(hubs.pop())
		i = i + 1
	hubs_per_pc = int(len(hubs)/PROCESS_COUNT)
	for pc in range(0,PROCESS_COUNT):
		sleep_time = config['interval'] * int((hubs_per_pc/config['per_count']))*pc
		start = hubs_per_pc*pc
		end =  hubs_per_pc*(pc+1)
		hub = hubs[start:end]
		str_hub = ','.join(hub)
		client_cfg['msg_type'] = 'config_res'
		client_cfg['sleep_time'] = sleep_time
		client_cfg['interval'] = config['interval']
		client_cfg['per_count'] = config['per_count']
		client_cfg['hubs'] = hub
		client_cfg['user'] = config['user']
		client_cfg['pwd'] = config['pwd']
		client_cfg['host'] = config['host']
		client_cfg['test_mode'] = config['test_mode']
		client_configs.append(str(client_cfg))

#设置请求头
def set_header():
	global headers,sethead_timer
	use_info = config['user']+':'+ config['pwd']
	#编码开发者帐号
	encode_info =base64.b64encode(use_info.encode('utf-8'))
	head = {
		'Content-Type': 'application/json',
		'Authorization': 'Basic '+ encode_info.decode("utf-8")
	}
	data = {'grant_type':'client_credentials'}
	try:
		#发起请求
		res = requests.post(config['host'] + '/oauth2/token', data= json.dumps(data),headers = head)
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
	sethead_timer = threading.Timer(3500,set_header)
	sethead_timer.start()

def connect_to_client(sock,addr):
	global data
	while True:
		if TESTING:
			try:
				data = sock.recv(1024)
			except Exception as e:
				# print(e)
				pass	
			message = str(data,encoding = 'utf-8')
			data_type = message.split('+')[0].strip()
			# print(data_type,message)
			send_para(sock,message,data_type,addr)
		else:
			break

def send_para(sock,data,data_type,addr):
	total_ap = 0
	total_speed = 0
	if data_type == 'config_req':
		sock.send(bytes(client_configs[config['process_no']],encoding = 'utf-8'))
		msg = {'msg_type':'session','session':config['process_no']}
		sock.send(bytes(str(msg),encoding = 'utf-8'))
	elif data_type == 'config_ok':
		config['process_no'] = config['process_no'] +1
		CLIENT_INFO.append({'speed':0,'scanning_aps':0})
		print("Client's %s:%s test parameters inited success！\n"%(addr[0],addr[1]))
		if config['process_no'] == config['process_count']:
			print('All pc has been inited success,test start !\n')
			start_test(CLIENTS)
	elif data_type == 'sync':
		session = int(data.split('+')[1])
		# print('session',session)
		speed = data.split('+')[2]
		scanning_aps = data.split('+')[3]
		CLIENT_INFO[session]['speed']=  speed	
		CLIENT_INFO[session]['scanning_aps']=  scanning_aps
		for c in CLIENT_INFO:
			total_speed = total_speed + int(c.get('scanning_aps')) * int(c.get('speed'))
			total_ap = total_ap + int(c.get('scanning_aps')) 
		if total_ap >0:
			aver_speed = total_speed / total_ap
			print('Scanning ap count is %d now,average scan speed is %d.\n'%(total_ap,aver_speed))
	elif data_type == 'bak_ap_scan':
		mac = data.split('+')[1].strip()
		print("Bak ap %s start scan success!\n"%mac)
	elif data_type == 5:
		pass
	elif data_type == 6:
		pass

def get_online_hubs(headers):
	res = requests.get(config['host'] + '/cassia/hubs',headers = headers)
	res_hub_info = json.loads(res.text)
	hubs = []
	for i in res_hub_info:
		hubs.append(i['mac'])
	return hubs

def get_scanning_ap():
	total = 0
	global SCANNING_APS
	while True:
		for hub in SCANNING_APS:
			total = total + len(hub)
		if total < len(hubs):
			for client in CLIENTS:
				client.send(bytes('scanning_aps_req',encoding = 'utf-8'))
				time.sleep(1)
			time.sleep(10)
			total = 0
		else:
			print('All AP has started scan success!')
			break

def hubStatus():
	global OFFLINE_APS
	try:
		hubstatus = requests.get(config['host'] + '/cassia/hubStatus',headers = headers,stream =True)
		for line in hubstatus.iter_lines():	
			if TESTING:		
				message = str(line,encoding='utf-8')		
				if message.startswith('data'):
					message = json.loads(message[6:])
					if OFFLINE_APS <config['max_offline']:#判断离线AP是否超过限制，如果超过则停止测试
						if message['status'] == 'offline':
							print('AP(%s)offline,will use backup AP ccontinue test！'%message['mac'])
							for hubs in config['max_offline']:
								if message['mac'] in hubs:
									session = SCANNING_APS.index(hubs)#定位到离线AP属于哪个client
									#向上面定位到的client发送备用AP，并开启扫描
									msg = {'msg_type':'bak_ap_scan','bak_aps':BAK_APS[OFFLINE_APS],'mac':message['mac']} 
									CLIENTS[session].send(bytes(str(msg),encoding='utf-8'))
									msg['msg_type'] = 'scanning_aps_req'
									CLIENTS[session].send(bytes(str(msg),encoding = 'utf-8'))
									OFFLINE_APS = OFFLINE_APS +1
					else:
						print('Too many AP offline,test failed ,stop!')
						msg = {'msg_type':'test_stop'}
						for client in CLIENTS:
							client.send(bytes(str(msg),encoding = 'utf-8'))
							client.close()
							time.sleep(1)
			else:
				break
	except Exception as e:
		print(e)

def stop_test(clients):
	global TESTING,COPY_TIMER
	TESTING = False
	sethead_timer.cancel()
	if config['test_mode'] == 0:
		try:
			COPY_TIMER.cancel()
		except:
			pass
	msg = {'msg_type':'test_stop'}
	for client in clients:
		client.send(bytes(str(msg),encoding = 'utf-8'))
		client.close()
		time.sleep(1)
	copy_file(False)

	# sys.exit(1)

def start_test(clients):
	global COPY_TIMER
	init_monitor_client()
	start_ac_monitor()
	if config['test_mode'] == 0:
		COPY_TIMER = threading.Timer(600,copy_file,args = (True,))
		COPY_TIMER.start()
	msg = {'msg_type':'test_start'}
	for client in clients:
		client.send(bytes(str(msg),encoding = 'utf-8'))
		time.sleep(1)
	threading.Thread(target = hubStatus).start()
	threading.Timer(config['test_time'],stop_test,args =(clients,)).start()

def start_ac_monitor():	#开始新的监控进程，生成全新的测试文件
	ip = config['host'].split('/')[2]
	test_time = config['test_time']
	if test_time>3600*3:
		interval = '30'
		count = str(int(int(test_time)/int(interval)))
	else:
		interval = '3'
		count = str(int(int(test_time)/int(interval)))
	cmd1 = '/tmp/nmon_x86_centos6 -f -N -m /tmp/res/ -s '+ interval +' -c '+count
	cmd2 = 'top -d '+interval+' -n '+count+' -b >>/tmp/res/monitor_data_top.txt 2>&1 &'
	cmd3 = 'pidstat -r '+interval+' '+count+' >>/tmp/res/monitor_data_mem.txt 2>&1 &'
	cmd4 = 'pidstat -d '+interval+' '+count+' >>/tmp/res/monitor_data_disk.txt 2>&1 &'
	try:
		if config['test_mode'] == '0':
			ssh_client.exec_command(cmd2)
			ssh_client.exec_command(cmd3)
			ssh_client.exec_command(cmd4)
		elif config['test_mode'] == '1':
			ssh_client.exec_command(cmd1)
			ssh_client.exec_command(cmd2)
		print('成功开启AC性能监控，数据文件保存在%s:/tmp/res/\n'%ip)
	except Exception as e:
		print('AC性能监控开启失败，\n',e)

def init_monitor_client():		#初始化性能监控工具
	global sftp_client,ssh_client
	ip = config['host'].split('/')[2]
	try:
		#初始化sftp客户端
		ftp = paramiko.Transport((ip,22))
		ftp.connect(username='root',password= config['ac_root_pwd'])
		sftp_client = paramiko.SFTPClient.from_transport(ftp)
		#初始化ssh客户端
		ssh_client = paramiko.SSHClient()
		ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
		ssh_client.connect(ip,22,'root',config['ac_root_pwd'],timeout=5)
		print('Monitor client init successed!\n')
	except Exception as e:
		print('Monitor client init failed!\n')
		print(e)
	try:
		sftp_client.put('nmon_x86_centos6','/tmp/nmon_x86_centos6')
	except Exception as e:
		print(e)
		print('自动上传nmon工具失败，请手动上传！')
	try:
		ssh_client.exec_command('killall top')
		ssh_client.exec_command('killall pidstat')
		ssh_client.exec_command('killall nmon_x86_centos6')
		ssh_client.exec_command('chmod 777 /tmp/nmon_x86_centos6')
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

#从AC拷贝数据文件
def copy_file(flag = True):
	global COPY_TIMER
	no = 0
	src = '/tmp/res/'
	print('开始从服务器拷贝文件到本地\n')
	try:
		files = sftp_client.listdir('/tmp/res/')
		for file in files:
			sftp_client.get(src+file,config['data_path']+file)
		print('成功从AC拷贝测试结果文件到目录%s\n'%config['data_path'])	
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
						sftp_client.get(src+file,config['data_path']+file)
				except Exception as e:
					print(e)
				no += 1
			print('从服务器copy文件失败，请手动copy\n',e)
			return

	write_csv()
	'''通过标志位判断是否继续调用自身，当停止测试最后一次调用时，flag应该为false,
		否则程序不能自动结束运行。
	'''
	if flag:
		COPY_TIMER = threading.Timer(600,copy_file,)
		COPY_TIMER.start()
	else:
		pass

#提取测试数据，并写入到data_path目录下的data.csv文件中 
def write_csv():
	data_path = config['data_path']
	for file in os.listdir(data_path):
		filename = file.split('.')[0]
		if filename == 'monitor_data_top':
			print('开始处理测试数据文件...\n')
			with open(data_path+file,'r',encoding = 'utf-8') as f:
				nfm_rows = [['name', 'CPU', 'MEM']]
				ac_rows = [['name', 'CPU', 'MEM']]
				mongod_rows = [['name', 'CPU', 'MEM']]
				node_rows = [['name', 'CPU', 'MEM']]
				cpu_total_rows = [['name', 'us', 'sy', 'id', 'wa', 'si']]
				mem_total_rows = [['name', 'free', 'used', 'total', 'buff']]
				nodes = {}
				for line in f:
					try:
						if 'NFM' in line:
							data = line.split()
							name, cpu, mem = data[11], data[8], data[9]
							nfm_rows.append([name, cpu, mem])
						elif 'node' in line:
							data = line.split()
							if data[0] in nodes:
								name, cpu, mem = data[11] + '_' + data[0], data[8], data[9]
								nodes.get(data[0]).append([name, cpu, mem])
							else:
								nodes[data[0]] = [['name', 'CPU', 'MEM']]
								name, cpu, mem = data[11] + '_' + data[0], data[8], data[9]
								nodes.get(data[0]).append([name, cpu, mem])
						elif 'AC' in line:
							data = line.split()
							name, cpu, mem = data[11], data[8], data[9]
							ac_rows.append([name, cpu, mem])
						elif 'mongod' in line:
							data = line.split()
							name, cpu, mem = data[11], data[8], data[9]
							mongod_rows.append([name, cpu, mem])
						elif line.startswith('Cpu'):
							data = line.split()
							cpu_total_rows.append(
								['CPU_total', data[1].split('%')[0], data[2].split('%')[0], data[4].split('%')[0],
								 data[5].split('%')[0], data[7].split('%')[0]])
						elif line.startswith('Mem'):
							data = line.split()
							mem_total_rows.append(
								['MEM_total', int(int(data[5][:-1]) / 1024), int(int(data[3][:-1]) / 1024),
								 int(int(data[1][:-1]) / 1024), int(int(data[7][:-1]) / 1024)])
					except:
						pass
				with open('top.csv', 'w', newline='') as f:
					csv_write = csv.writer(f, dialect='excel')
					min_len = min(len(ac_rows), len(nfm_rows), len(mongod_rows), len(mem_total_rows),
								  len(cpu_total_rows))
					for i in range(min_len):
						row = []
						node = [x[i] for _, x in nodes.items()]
						for x in node:
							for y in x:
								row.append(y)
						L = ac_rows[i] + nfm_rows[i] + mongod_rows[i] + mem_total_rows[i] + cpu_total_rows[i] + row
						csv_write.writerow(L)
			print('数据处理完成，结果文件到目录C:/Users/Administrator/Desktop/\n')


def main():
	global CLIENTS
	init_config()
	init_para()
	sk = socket.socket()
	try:
		localIP = socket.gethostbyname(socket.gethostname())#获取本机IP，windows
	except:	
		try:
			#获取本机IP，linux
			localIP = socket.inet_ntoa(fcntl.ioctl(s.fileno(), 0x8915, struct.pack('256s', ifname[:15]))[20:24])
		except:
			print('Get host IP failed！！！')
	sk.bind((localIP,8080))
	sk.listen(5)
	print("#######################################################")
	print("Monitor stared,listening on %s waiting for client connect...."%localIP)
	print("#######################################################")
	while True:
		try:
			sock,addr = sk.accept()
			CLIENTS.append(sock)
			print('New connect from :',addr)
			threading.Thread(target= connect_to_client,args =(sock,addr)).start()
		except Exception as e:
			print(e)
		time.sleep(1)
		if config['process_no'] == config['process_count']:
			break

if __name__ == '__main__':

	main()