# -*- coding: utf-8 -*-

from urllib import request
from bs4 import BeautifulSoup
import os
import re
import queue
import threading
import urllib
from retry import retry
import random

"""
下载听歌网站的所有歌曲
"""
ROOT_DIR = "H:\\music\\"
INDEX_URL = "http://www.yymp3.com/"
DOWNLOAD_URL = "http://ting666.yymp3.com:86/"
DEFAULT_TIMEOUT = 60
DEFAULT_RETRY_TIMES = 3
DEFAULT_RETRY_DELAY = 3
DEFAULT_THREAD_COUNT = 10

USER_AGENT_LIST = [
 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) '
  'Chrome/45.0.2454.85 Safari/537.36 115Browser/6.0.3',
 'Mozilla/5.0 (Macintosh; U; Intel Mac OS X 10_6_8; en-us) AppleWebKit/534.50 (KHTML, like Gecko) Version/5.1 Safari/534.50',
 'Mozilla/5.0 (Windows; U; Windows NT 6.1; en-us) AppleWebKit/534.50 (KHTML, like Gecko) Version/5.1 Safari/534.50',
 'Mozilla/4.0 (compatible; MSIE 8.0; Windows NT 6.0; Trident/4.0)',
 'Mozilla/4.0 (compatible; MSIE 7.0; Windows NT 6.0)',
 'Mozilla/5.0 (Windows NT 6.1; rv:2.0.1) Gecko/20100101 Firefox/4.0.1',
 'Opera/9.80 (Windows NT 6.1; U; en) Presto/2.8.131 Version/11.11',
 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_7_0) AppleWebKit/535.11 (KHTML, like Gecko) Chrome/17.0.963.56 Safari/535.11',
 'Mozilla/4.0 (compatible; MSIE 7.0; Windows NT 5.1; Trident/4.0; SE 2.X MetaSr 1.0; SE 2.X MetaSr 1.0; .NET CLR 2.0.50727; SE 2.X MetaSr 1.0)',
 'Mozilla/5.0 (compatible; MSIE 9.0; Windows NT 6.1; Trident/5.0',
 'Mozilla/5.0 (Windows NT 6.1; rv:2.0.1) Gecko/20100101 Firefox/4.0.1',
]

R_INVALID_FILE_NAME_CHAR = r"[\/\\\:\*\?\"\<\>\|]"  # '/ \ : * ? " < > |'


class MusicDowndloader:
	def __init__(self, url=''):
		self.music_info_list = []
		self.url = url
		self.music_info_queue = queue.Queue(1000)
		self.stop = False
		self.header = {
			"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/59.0.3071.115 Safari/537.36"}
	
	# 请求网页得到BeautifulSoup对象
	@retry(tries=3, delay=3)
	def get_beautiful_soap(self, url):
		try:
			# 随机UA
			req = request.Request(url, headers={"User-Agent": random.choice(USER_AGENT_LIST)})
			res = request.urlopen(req, timeout=DEFAULT_TIMEOUT)
			# 以html5lib格式的解析器解析得到BeautifulSoup对象
			# 还有其他的格式如：html.parser/lxml/lxml-xml/xml/html5lib
			soup = BeautifulSoup(res, 'html5lib')
			return soup
		except urllib.error.URLError as error:
			print("get_beautiful_soap ERROR:%s" % error)
		except urllib.error.HTTPError as error:
			print("get_beautiful_soap ERROR:%s" % error)
			
	# 大分类 内地男歌手 内地女歌手...
	# 输入 http://www.yymp3.com/
	# 抽取 ("-1", "1", "内地男歌手", "http://example.com/Art/1_1.html")
	def get_type_level_1(self, url):
		soup = self.get_beautiful_soap(url)
		if soup is None:
			print('soup is None, url: %s' % url)
			return []
		type_levels = soup.findAll(href=re.compile("/Art"))
		id = 0
		music_type_1_list = []
		for level in type_levels:
			id += 1
			# (parent_id,id,type,href)
			# (-1, 1, "内地男歌手", "http://example.com/Art/1_1.html")
			music_type_1_list.append(("-1", str(id), level.text, self.url + level['href']))
		return music_type_1_list
			
	# 二级分类  内地男歌手-->陈星
	# ("-1", "1", "内地男歌手", "http://example.com/Art/1_1.html")
	# ("1", "1_1", "内地男歌手@@@陈星", "http://example.com/Singer/10717.htm")
	def get_type_level_2(self, url, parent_type_name, parent_id):
		soup = self.get_beautiful_soap(url)
		if soup is None:
			print('soup is None, url: %s' % url)
			return []
		id = 0
		music_type_2_list = []
		# 获得按首字母分类列表
		cate_by_letter = soup.findAll('ul', 'Cate_slist c')
		for cate in cate_by_letter:
			# 获得歌星列表
			cate_list = cate.findAll('a')
			for cate_one in cate_list:
				id += 1
				# (1, 1_1, "内地男歌手@@@陈星", "http://example.com/Singer/10717.htm")
				music_type_2_list.append((parent_id, parent_id + "_" + str(id), parent_type_name + "@@@" + cate_one.text, self.url + cate_one['href']))
		return music_type_2_list
			
	# 三级分类 内地男歌手-->陈星--->专辑列表
	# # ("1", "1_1", "内地男歌手@@@陈星", "http://example.com/Singer/10717.htm")
	# # ("1_1", "1_1_1", "内地男歌手@@@陈星@@@北漂", "http://example.com/Album/5620.htm")
	def get_type_level_3(self, url, parent_type_name, parent_id):
		soup = self.get_beautiful_soap(url)
		if soup is None:
			print('soup is None, url: %s' % url)
			return []
		# parent_type_name = url_tuple[2]
		# parent_id = url_tuple[1]
		id = 0
		music_type_3_list = []
		# 获取专辑列表
		album_list = soup.findAll('a', 'A_name')
		for album in album_list:
			id += 1
			# (1_1, 1_1_1, "内地男歌手@@@陈星@@@北漂", "http://example.com/Album/5620.htm")
			music_type_3_list.append((parent_id, parent_id + "_" + str(id), parent_type_name + "@@@" + album.text, self.url + album['href']))
		
		return music_type_3_list
			
	# 四级分类 内地男歌手-->韩磊--->专辑列表--->歌曲名
	# ("1_1", "1_1_1", "内地男歌手@@@陈星@@@北漂", "http://example.com/Album/5620.htm")
	# ("1_1", "1_1_1", "内地男歌手@@@陈星@@@北漂", "http://www.yymp3.com/Play/5620/69902.htm")
	def get_type_level_4(self, url, parent_type_name, parent_id):
		soup = self.get_beautiful_soap(url)
		if soup is None:
			print('soup is None, url: %s' % url)
			return []
		# parent_type_name = url_tuple[2]
		# parent_id = url_tuple[1]
		id = 0
		music_url_list = []
		# 获取专辑页面中，歌曲列表
		music_list = soup.findAll("span", "s2")
		for music in music_list:
			# 歌曲url
			music_a = music.find('a')
			if music_a:
				id += 1
				# (1_1, 1_1_1, "内地男歌手@@@陈星@@@北漂", "http://www.yymp3.com/Play/5620/69902.htm")
				music_url_list.append((parent_id, parent_id + "_" + str(id), parent_type_name, self.url + music_a['href']))
		
		return music_url_list
	
	# 爬取歌曲页面，并设置保存目录
	# # ("1_1", "1_1_1", "内地男歌手@@@陈星@@@北漂", "http://www.yymp3.com/Play/5620/69902.htm")
	# # ("ROOT_DIR//内地男歌手//陈星//北漂", "农民.mp3", "http://ting666.yymp3.com:86/new11/tlfy/6.mp3")
	def get_music_info(self,  url, parent_type_name):
		soup = self.get_beautiful_soap(url)
		if soup is None:
			print('soup is None, url: %s' % url)
			return
		# parent_type_name = url_tuple[2]
		try:
			# script标签中包含song_data字符串的话，此script就是我们需要的
			music_data_script = soup.findAll('script')
			for script in music_data_script:
				if script.text.rfind('song_data') != -1:
					music_data = script.text.split("|")
					# 歌名中包含"/"将会报错，无法创建文件
					music_url = music_data[4].lower().replace(".wma", ".mp3")
					# ("ROOT_DIR\\内地男歌手\\陈星\\北漂", "农民.mp3", "http://ting666.yymp3.com:86/new11/tlfy/6.mp3")
					# 特殊字符无法创建目录
					# 特殊字符统一替换掉，避免创建文件或文件夹出错
					type_name = replace_invalid_str(parent_type_name).replace("@@@", "\\")
					music_path = ROOT_DIR + type_name
					self.music_info_queue.put((music_path, replace_invalid_str(music_data[1]) + ".mp3", DOWNLOAD_URL + music_url), True)
					break
		except IndexError as e:
			print("ERROR in get_music_info: %s, url: %s" % (e, url))
		
	# 下载歌曲文件
	@retry(tries=3, delay=3)
	def download_music(self):
		while self.music_info_queue.not_empty and not self.stop:
			try:
				url_tuple = self.music_info_queue.get(True)
				music_url = url_tuple[-1]
				music_dir = url_tuple[0]
				mk_dirs_for_music(music_dir)
				music_name = url_tuple[1].replace("/", "&")
				print("music_url: %s, music_name: %s " % (music_url, music_name))
			
				music_full_path = music_dir + "\\" + music_name
				if not os.path.exists(music_full_path):
					with request.urlopen(music_url) as web:
						# 为保险起见使用二进制写文件模式，防止编码错误
						with open(music_full_path, 'wb') as outfile:
							outfile.write(web.read())
							outfile.close()
			except IOError as e:
				print("ERROR:%s " % e)
		
		print("结束爬虫")
	
	"""根据类型下载  http://www.yymp3.com/Art/10_24.html"""
	# 提供此函数，用于手动按歌星分类下载歌曲
	def get_music_by_art(self, path, url):
		try:
			soup = self.get_beautiful_soap(url)
			cate_by_letter = soup.findAll('ul', 'Cate_slist c')
			for cate in cate_by_letter:
				# 获得歌星列表
				cate_list = cate.findAll('a')
				for cate_one in cate_list:
					self.get_music_by_author(path + "\\" + replace_invalid_str(cate_one.text), self.url + cate_one['href'])
		except IOError as e:
			print("ERROR: %s" % e)
	
	"""根据歌手下载  http://www.yymp3.com/Singer/10817.htm"""
	# 提供此函数，用于手动按歌星下载歌曲
	def get_music_by_author(self, path, url):
		try:
			
			soup = self.get_beautiful_soap(url)
			# 获取专辑列表
			album_list = soup.findAll('a', 'A_name')
			for album in album_list:
				# 根据专辑下载
				self.get_music_by_album(path + "\\" + replace_invalid_str(album.text), self.url + album['href'])
		except IOError as e:
			print("ERROR: %s" % e)
	
	"""根据专辑下载  http://www.yymp3.com/Album/23252.htm"""
	# 提供此函数，用于手动按专辑下载歌曲
	def get_music_by_album(self, path, url):
		try:
			soup = self.get_beautiful_soap(url)
			# 获取专辑页面中，歌曲列表
			music_list = soup.findAll("span", "s2")
			for music in music_list:
				# 歌曲url
				music_a = music.find('a')
				if music_a:
					self.direct_download(path, self.url + music_a['href'])
		except IOError as e:
			print("ERROR: %s" % e)
	
	"""根据url直接下载歌曲"""
	# 提供此函数，用于手动按歌曲url下载歌曲
	def direct_download(self, path, url):
		soup = self.get_beautiful_soap(url)
		try:
			music_data_script = soup.findAll('script')
			for script in music_data_script:
				if script.text.rfind('song_data') != -1:
					music_data = script.text.split("|")
					music_url = music_data[4].lower().replace(".wma", ".mp3")
					music_url = DOWNLOAD_URL + music_url
					type_name = path.replace("@@@", "\\")
					music_name = replace_invalid_str(music_data[1]) + ".mp3"
					mk_dirs_for_music(type_name)
					print("music_url: %s, music_name: %s " % (music_url, music_name))
					
					music_full_path = type_name + "\\" + music_name
					if not os.path.exists(music_full_path):
						with request.urlopen(music_url) as web:
							# 为保险起见使用二进制写文件模式，防止编码错误
							with open(music_full_path, 'wb') as outfile:
								outfile.write(web.read())
								outfile.close()
					break
		except IndexError as e:
			print("ERROR in get_music_info: %s, url: %s" % (e, url))
		except IOError as ioe:
			print("ERROR: %s" % ioe)
	
	
# 根据信息创建歌曲分类文件夹
def mk_dirs_for_music(self, dirs):
	if not os.path.exists(dirs):
		print("创建目录:%s" % dirs)
		os.makedirs(dirs, exist_ok=True)


# 获取已经下载过的歌曲列表
# 传入一个路径列表，返回其下一级路径的列表
#
# 使用场景：爬虫运行中，可能卡死，重启下载需要忽略已下载的部分，目前只过滤到第二级，如"内地男歌手-->韩大锤"，
# 如果在内地男歌手分类下，已经存在韩大锤这个目录，将直接跳过，不再下载他的所有歌曲
def get_exist_dir(dir_list):
	ret_list = []
	if dir_list:
		for temp_dir in dir_list:
			# 对遍历出来的多个目录list进行合并
			ret_list.extend(os.listdir(temp_dir))
	return ret_list


# 获取音乐目录列表
def get_path(*args):
	path_list_temp = []
	for arg in args:
		for filename in os.listdir(arg):
			path_list_temp.append(os.path.join(arg, filename))
		
	return path_list_temp


# 替换特殊字符（将导致创建文件或路径非法的字符）
def replace_invalid_str(info):
	return re.sub(R_INVALID_FILE_NAME_CHAR, "&", info)


if __name__ == '__main__':
	# 下载特定分类歌曲
	# music_downloader = MusicDowndloader(INDEX_URL)
	# music_downloader.get_music_by_art('h:\\music\\喊麦\\', 'http://www.yymp3.com/Art/10_20.html')
	# pass
	# 结束：下载特定分类歌曲
	
	# 开十个线程下载
	music_downloader = MusicDowndloader(INDEX_URL)
	thread_count = 0
	while thread_count < DEFAULT_THREAD_COUNT:
		t = threading.Thread(target=music_downloader.download_music)
		t.setName("Thread" + str(thread_count))
		t.start()
		thread_count += 1

	music_type_1_list = music_downloader.get_type_level_1(music_downloader.url)
	# 找出已经下载过的歌曲目录，重复启动爬虫下载时，自动过滤掉，避免多余的请求
	# path_list_all = get_path('H:\\music\\', 'F:\\music\\', 'G:\\music\\', 'E:\\entermainment\\music\\yymp3\\')
	# exist_path_list = get_exist_dir(path_list_all)
	exist_path_list = []
	for music_type_1 in music_type_1_list:
		print("一级分类：-%s" % music_type_1[2])
		music_type_2_list = music_downloader.get_type_level_2(music_type_1[-1], music_type_1[2], music_type_1[1])
		for music_type_2 in music_type_2_list:
			ex_dir = music_type_2[2].split("@@@")[1]
			if exist_path_list.__len__() > 0 and exist_path_list.__contains__(ex_dir):
				print("已存在二级分类：--%s" % music_type_2[2])
				exist_path_list.remove(ex_dir)
			else:
				print("二级分类：--%s" % music_type_2[2])
				music_type_3_list = music_downloader.get_type_level_3(music_type_2[-1], music_type_2[2], music_type_2[1])
				for music_type_3 in music_type_3_list:
					print("三级分类：---%s" % music_type_3[2])
					music_url_list = music_downloader.get_type_level_4(music_type_3[-1], music_type_3[2], music_type_3[1])
					for music_url in music_url_list:
						music_downloader.get_music_info(music_url[-1], music_url[-2])
	music_downloader.stop = True
