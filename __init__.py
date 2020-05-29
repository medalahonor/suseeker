from gevent import monkey

monkey.patch_ssl()
monkey.patch_socket()
monkey.patch_dns()


import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)