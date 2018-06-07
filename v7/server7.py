import requests
import base64
import json
import threading
import re
import time
import socket
import sys,os
import paramiko,csv


PROCESS_NO = 0		#连接服务器的测试进程序列号
CLIENTS = []
client_config = []
hubs = 0
# SCANNING_APS = []	#二维数组，春初每个client当前的扫描AP数量
BAK_APS = []
OFFLINE_APS = 0
CLIENT_INFO = []
TESTING = True

def init_config():
    global HOST,user,pwd,INTERVAL,PER_COUNT,MAX_OFFLINE,PROCESS_COUNT,test_time,run_mode,ac_root_pwd,data_path
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
                            HOST = value
                        elif key == 'user':
                            user = value
                        elif key =='pwd':
                            pwd = value
                        elif key =='PROCESS_COUNT':
                            PROCESS_COUNT = int(value)
                        elif key == 'PROCESS_NO':
                            PROCESS_NO = int(value)
                        elif key == 'INTERVAL':
                            INTERVAL =int(value)
                        elif key == 'PER_COUNT':
                            PER_COUNT = int(value)
                        elif key =='test_time':
                            test_time = int(value)
                        elif key =='MAX_OFFLINE':
                            MAX_OFFLINE = int(value)
                        elif key == 'run_mode':
                            run_mode = value
                        elif key == 'ac_root_pwd':
                            ac_root_pwd = value
                        elif key =='data_path':
                            data_path = value
                        else:
                            pass
    except Exception as e:
        print('配置文件打开失败',e)

def init_para():
    global client_config,hubs,BAK_APS
    i =0
    set_header()
    hubs = get_online_hubs(headers)
    while i<MAX_OFFLINE:
        BAK_APS.append(hubs.pop())
        i = i + 1
    hubs_per_pc = int(len(hubs)/PROCESS_COUNT)
    for pc in range(0,PROCESS_COUNT):
        sleep_time = INTERVAL * int((hubs_per_pc/PER_COUNT))*pc
        start = hubs_per_pc*pc
        end =  hubs_per_pc*(pc+1)
        hub = hubs[start:end]
        str_hub = ','.join(hub)
        client_config.append('config_res'+'+'+str(sleep_time)+'+'+str(INTERVAL)+'+'+str(PER_COUNT)+
            "+"+str_hub+'+'+user+'+'+pwd+'+'+HOST+'+'+run_mode)

#设置请求头
def set_header():
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
    sethead_timer = threading.Timer(3500,set_header)
    sethead_timer.start()

def connect_to_client(sock,addr):
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
    global PROCESS_COUNT,PROCESS_NO
    if data_type == 'config_req':
        sock.send(bytes(client_config[PROCESS_NO],encoding = 'utf-8'))
        sock.send(bytes('session +'+str(PROCESS_NO),encoding = 'utf-8'))
    elif data_type == 'config_ok':
        PROCESS_NO = PROCESS_NO +1
        CLIENT_INFO.append({'speed':0,'scanning_aps':0})
        print("Client's %s:%s test parameters inited success！\n"%(addr[0],addr[1]))
        if PROCESS_NO == PROCESS_COUNT:
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
    res = requests.get(HOST + '/cassia/hubs',headers = headers)
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
        # noinspection PyTypeChecker
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
        hubstatus = requests.get(HOST + '/cassia/hubStatus',headers = headers,stream =True)
        for line in hubstatus.iter_lines():
            if TESTING:
                message = str(line,encoding='utf-8')
                if message.startswith('data'):
                    message = json.loads(message[6:])
                    if OFFLINE_APS <MAX_OFFLINE:#判断离线AP是否超过限制，如果超过则停止测试
                        if message['status'] == 'offline':
                            print('AP(%s)offline,will use backup AP ccontinue test！'%message['mac'])
                            for hubs in SCANNING_APS:
                                if message['mac'] in hubs:
                                    session = SCANNING_APS.index(hubs)#定位到离线AP属于哪个client
                                    #向上面定位到的client发送备用AP，并开启扫描
                                    CLIENTS[session].send(bytes('bak_ap_scan+'+BAK_APS[OFFLINE_APS]+'+'+message['mac'],encoding='utf-8'))
                                    CLIENTS[session].send(bytes('scanning_aps_req',encoding = 'utf-8'))
                                    OFFLINE_APS = OFFLINE_APS +1
                    else:
                        print('Too many AP offline,test failed ,stop!')
                        for client in CLIENTS:
                            client.send(bytes('test_stop',encoding = 'utf-8'))
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
    if run_mode == '0':
        try:
            COPY_TIMER.cancel()
        except:
            pass
    for client in clients:
        client.send(bytes('test_stop',encoding = 'utf-8'))
        client.close()
        time.sleep(1)
    copy_file(False)

    # sys.exit(1)

def start_test(clients):
    global COPY_TIMER
    init_monitor_client()
    start_ac_monitor()
    if run_mode == '0':
        # noinspection PyTypeChecker
        COPY_TIMER = threading.Timer(600,copy_file,args = (True,))
        COPY_TIMER.start()
    for client in clients:
        client.send(bytes('test_start',encoding = 'utf-8'))
        time.sleep(1)
    threading.Thread(target = hubStatus).start()
# noinspection PyTypeChecker
threading.Timer(test_time,stop_test,args =(clients,)).start()

def start_ac_monitor():	#开始新的监控进程，生成全新的测试文件
    ip = HOST.split('/')[2]
    if test_time>3600*3:
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

def init_monitor_client():		#初始化性能监控工具
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
    except Exception as e:
        print('Monitor client init failed!\n')
        print(e)
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
    if len(history_files)>0:
        print('删除历史遗留数据文件!\n')
        for file in history_files:
            sftp_client.remove(src+file)

#从AC拷贝数据文件
def copy_file(flag = True):
    global data_path,COPY_TIMER
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
        COPY_TIMER = threading.Timer(600,copy_file,)
        COPY_TIMER.start()
    else:
        pass

#提取测试数据，并写入到data_path目录下的data.csv文件中 
def write_csv():
    for file in os.listdir(data_path):
        filename = file.split('.')[0]
        if filename == 'monitor_data_top':
            print('开始处理测试数据文件...\n')
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
        if PROCESS_NO == PROCESS_COUNT:
            break

if __name__ == '__main__':

    main()