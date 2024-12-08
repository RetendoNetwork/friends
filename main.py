# idk if this friends server works, but we will test it soon.

from nintendo.nex import rmc, kerberos, friends, \
	authentication, common, settings, secure
import os
from anyio import Lock
from pymongo.collection import Collection
import collections
import secrets
import aioconsole
import itertools
import asyncio
from dotenv import load_dotenv

import logging
logger = logging.getLogger(__name__)

load_dotenv()

ACCESS_KEY = "ridfebb9"
NEX_VERSION = 10100 # TODO - Maybe correct?
SECURE_SERVER = "Quazal Rendez-Vous"

User = collections.namedtuple("User", "pid name password")

users = [
	User(2, SECURE_SERVER, os.getenv("FRIENDS_PASSWORD")),
	User(100, "guest", "MMQea3n!fsik")
]

def get_user_by_name(name):
	for user in users:
		if user.name == name:
			return user
			
def get_user_by_pid(pid):
	for user in users:
		if user.pid == pid:
			return user
			
def derive_key(user):
	deriv = kerberos.KeyDerivationOld(65000, 1024)
	return deriv.derive_key(user.password.encode("ascii"), user.pid)

class AuthenticationServer(authentication.AuthenticationServer):
	def __init__(self, settings):
		super().__init__()
		self.settings = settings
	
	async def login(self, client, username):
		print("User trying to log in:", username)
		
		user = get_user_by_name(username)
		if not user:
			raise common.RMCError("RendezVous::InvalidUsername")
			
		server = get_user_by_name(SECURE_SERVER)
		
		url = common.StationURL(
			scheme="prudps", address=os.getenv("SERVER_IP_ADDR"), port=os.getenv("AUTHENTICATION_SERVER_PORT"),
			PID = server.pid, CID = 1, type = 2,
			sid = 1, stream = 10
		)
		
		conn_data = authentication.RVConnectionData()
		conn_data.main_station = url
		conn_data.special_protocols = []
		conn_data.special_station = common.StationURL()
		
		response = rmc.RMCResponse()
		response.result = common.Result.success()
		response.pid = user.pid
		response.ticket = self.generate_ticket(user, server)
		response.connection_data = conn_data
		response.server_name = "Retendo MK8 Server"
		return response
		
	def generate_ticket(self, source, target):
		settings = self.settings
		
		user_key = derive_key(source)
		server_key = derive_key(target)
		session_key = secrets.token_bytes(settings["kerberos.key_size"])
		
		internal = kerberos.ServerTicket()
		internal.timestamp = common.DateTime.now()
		internal.source = source.pid
		internal.session_key = session_key
		
		ticket = kerberos.ClientTicket()
		ticket.session_key = session_key
		ticket.target = target.pid
		ticket.internal = internal.encrypt(server_key, settings)
		
		return ticket.encrypt(user_key, settings)
	
class SecureConnectionServer(secure.SecureConnectionServer):
    def __init__(self, sessions_db: Collection):
        super().__init__()
        self.connection_id_counter = 1
        self.connection_id_lock = Lock()
        self.sessions_db = sessions_db
        self.clients = {}

    def transform_urls(self, urls: list[common.StationURL]) -> list[str]:
        return list(map(str, urls))

    def set_session_for_pid(self, pid: int, urls: list[common.StationURL], cid: int, addr: tuple[str, int]):
        url_list = self.transform_urls(urls)
        self.sessions_db.update_one({"pid": pid}, {"$set": {
            "pid": pid,
            "cid": cid,
            "urls": url_list,
            "ip": addr[0],
            "port": addr[1]
        }}, upsert=True)

    async def register(self, client: rmc.RMCClient, urls: list[common.StationURL]):
        url_list = urls.copy()
        public_url = url_list[0].copy()
        async with self.connection_id_lock:
            cid = self.connection_id_counter
            client.client.user_cid = cid
            self.clients[cid] = client

            self.connection_id_counter += 1
        remote_addr = client.remote_address()
        public_url["address"] = remote_addr[0]
        public_url["port"] = remote_addr[1]

        public_url["natf"] = 0
        public_url["natm"] = 0
        public_url["type"] = 3
        public_url["PID"] = client.pid()
        url_list.append(public_url)
        self.set_session_for_pid(client.pid(), url_list, cid, remote_addr)
        response = rmc.RMCResponse()
        response.result = common.Result.success()
        response.connection_id = cid
        response.public_station = public_url
        return response

    async def register_ex(self, client: rmc.RMCClient, urls: list[common.StationURL], login_data):
        return self.register(client, urls)

class FriendsServer(friends.FriendsServerV1):
    def __init__(self):
        super(FriendsServer, self).__init__()

    def get_all_information(self, context, nna_info, presence, birthday):
        logger.info("FriendsServer.get_all_information(pid: %d, call_id: %d, nna_info: %s, presence: %s, birthday: %s" % (context.pid, context.client.call_id, nna_info, presence, birthday))
        principal_preference = friends.PrincipalPreference()
        principal_preference.unk1 = True
        principal_preference.unk2 = True
        principal_preference.unk3 = False

        comment = friends.Comment()
        comment.unk = 0
        comment.text = ""
        comment.changed = common.DateTime(0)

        response = rmc.RMCResponse()
        response.principal_preference = principal_preference
        response.comment = comment
        response.friends = []
        response.sent_requests = []
        response.received_requests = []
        response.blacklist = []
        response.unk1 = False
        response.notifications = []
        response.unk2 = False
        return response

    def update_presence(self, context, presence):
        logger.info("FriendsServer.update_presence not implemented")
        raise common.RMCError("Core::NotImplemented")

async def main():
    s = settings.load('friends')
    s.configure(ACCESS_KEY, NEX_VERSION)

    auth_servers = [
		AuthenticationServer(s)
	]
    secure_servers = [
		SecureConnectionServer(sessions_db="sessions"),
		FriendsServer()
	]

    server_key = derive_key(get_user_by_name(SECURE_SERVER))
    async with rmc.serve(s, auth_servers, os.getenv("SERVER_IP_ADDR"), os.getenv("AUTHENTICATION_SERVER_PORT")):
    	async with rmc.serve(s, secure_servers, os.getenv("SERVER_IP_ADDR"), os.getenv("SECURE_SERVER_PORT"), key=server_key):
            print("== Friends Server ==")
            print("|", os.getenv("SERVER_IP_ADDR"), ":", os.getenv("AUTHENTICATION_SERVER_PORT"), "|")
            print("|", os.getenv("SERVER_IP_ADDR"), ":", os.getenv("SECURE_SERVER_PORT"),         "|")
            print("==================")
            await aioconsole.ainput("Press ENTER to close..\n")

asyncio.run(main())
