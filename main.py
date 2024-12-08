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
			scheme="prudps", address=os.getenv("FRIENDS_SERVER_IP"), port=os.getenv("AUTHENTICATION_SERVER_PORT"),
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
		response.server_name = "Retendo Friends Server"
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
		FriendsServer()
	]

    server_key = derive_key(get_user_by_name(SECURE_SERVER))
    async with rmc.serve(s, auth_servers, os.getenv("FRIENDS_SERVER_IP"), os.getenv("AUTHENTICATION_SERVER_PORT")):
    	async with rmc.serve(s, secure_servers, os.getenv("FRIENDS_SERVER_IP"), os.getenv("SECURE_SERVER_PORT"), key=server_key):
            print("== Friends Server ==")
            print("|", os.getenv("FRIENDS_SERVER_IP"), ":", os.getenv("AUTHENTICATION_SERVER_PORT"), "|")
            print("|", os.getenv("FRIENDS_SERVER_IP"), ":", os.getenv("SECURE_SERVER_PORT"),         "|")
            print("==================")
            await aioconsole.ainput("Press ENTER to close..\n")

asyncio.run(main())
