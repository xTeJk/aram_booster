from lcu_driver import Connector
import time, datetime
import requests, json, re, os, psutil, subprocess
from requests.packages.urllib3.exceptions import InsecureRequestWarning

connector = Connector()

debug_mode = False

# LCU DATA
LCU_PORT = 0
LCU_PASSWORD = ""
GAME_VERSION = ""

# ACCOUNT DATA
ACCOUNT_ID = 0
CURRENT_RP = 0

# STORE
STORE_URL = ""
JWT_TOKEN = []
ACCESS_TOKEN = ""
old_jwt_file = os.path.join(os.getcwd(), 'take_ab.json')


def IsLeagueRunning():
	for proc in psutil.process_iter(['name']):
		if proc.info['name'] == "LeagueClientUx.exe":
			return True
	return False


async def getData(connection):
	if connection:
		global LCU_PORT, LCU_PASSWORD, GAME_VERSION, ACCOUNT_ID, CURRENT_RP, CHAMP_TO_BUY

	# GET LCU PORT
		command = "WMIC PROCESS WHERE name='LeagueClientUx.exe' GET commandline"
		output = subprocess.Popen(command, stdout=subprocess.PIPE, shell=True).stdout.read().decode('utf-8')
		LCU_PORT = re.findall(r'"--app-port=(.*?)"', output)[0]

		if (debug_mode):
			print(f"» LCU PORT: {LCU_PORT}")

	# GET LCU PASSWORD
		LCU_PASSWORD = re.findall(r'"--remoting-auth-token=(.*?)"', output)[0]
		if (debug_mode):
			print(f"» LCU PASSWORD: {LCU_PASSWORD}")

	# GET GAME VERSION
		if os.path.exists(old_jwt_file):
			with open(old_jwt_file, 'r') as f:
				data = json.load(f)
				GAME_VERSION = data["GAME_VERSION"]
				if GAME_VERSION == "SET_CLIENT_GAME_VERSION_HERE__WITHOUT_V - https://prnt.sc/esaDdcJAX9H8":
					print("\n» PLEASE SET CLIENT GAME VERSION IN THE take_ab.json FILE!")
					input("")
					exit()
				
				if (debug_mode):
					print(f"» GAME VERSION: {GAME_VERSION}")

	# ACCOUNT INFO
		session = await connection.request("GET", "/lol-login/v1/session")
		if session.status == 200:
			session_data = await session.json()
			ACCOUNT_ID = session_data['accountId']

			if (debug_mode):
				print(f"» Account ID: {session_data['accountId']}")

		summoner = await connection.request("GET", "/lol-summoner/v1/current-summoner")
		if summoner.status == 200:
			summoner_data = await summoner.json()

			if (debug_mode):
				print(f"» Name: {summoner_data['displayName']}")
		
		wallet = await connection.request("GET", "/lol-store/v1/wallet")
		if wallet.status == 200:
			wallet_data = await wallet.json()
			CURRENT_RP = wallet_data['rp']

			if (debug_mode):
				print (f"» RP: {wallet_data['rp']} || BE: {wallet_data['ip']}")


async def getStoreData(connection):
	global JWT_TOKEN, ACCESS_TOKEN, STORE_URL, ACCOUNT_ID, GAME_VERSION
	if connection:
		# GET STORE URL
		storeURL = await connection.request("GET", "/lol-store/v1/getStoreUrl")
		if storeURL.status == 200:
			STORE_URL = await storeURL.json()

			if (debug_mode):
				print("» STORE URL: {sURL_data}")

		# GET WALLET JWT
		## CHECK IF OLD JWT EXISTS
		if os.path.exists(old_jwt_file):
			with open(old_jwt_file, 'r') as f:
				data = json.load(f)

				if ACCOUNT_ID not in data:
					walletJwt = await connection.request("GET", "/lol-inventory/v1/signedWallet/RP")
					if walletJwt.status == 200:
						wallet_data = await walletJwt.json()
						JWT_TOKEN.append((wallet_data["RP"], int(time.time())))

					data[ACCOUNT_ID] = {
						"JWT": JWT_TOKEN[0][0],
						"TIME": int(time.time()),
					}

					with open(old_jwt_file, 'w') as f:
						json.dump(data, f, indent=4)

					if (debug_mode):
						print(f"» NEW WALLET JWT: {wallet_data['RP']}")
				else:
					old_jwt_time = data[f"{ACCOUNT_ID}"].get("TIME")
					saved_date = datetime.datetime.fromtimestamp(old_jwt_time)
					current_date = datetime.datetime.now()

					if saved_date.day == current_date.day:
						JWT_TOKEN.append((data.get(f"{ACCOUNT_ID}").get("JWT"), old_jwt_time))
						if (debug_mode):
							print(f"» OLD WALLET JWT: {JWT_TOKEN[0][0]}")
					else: ## CREATE NEW JWT IF OLD IS OUTDATED
						walletJwt = await connection.request("GET", "/lol-inventory/v1/signedWallet/RP")
						if walletJwt.status == 200:
							wallet_data = await walletJwt.json()
							JWT_TOKEN.append((wallet_data["RP"], int(time.time())))

							## UPDATE CACHE FILE
							data[f"{ACCOUNT_ID}"]["JWT"] = wallet_data["RP"]
							data[f"{ACCOUNT_ID}"]["TIME"] = int(time.time())
							with open(old_jwt_file, 'w') as f:
								json.dump(data, f, indent=4)

							if (debug_mode):
								print(f"» NEW WALLET JWT: {wallet_data['RP']}")
		else: ## CREATE JWT AND CACHE FILE
			walletJwt = await connection.request("GET", "/lol-inventory/v1/signedWallet/RP")
			if walletJwt.status == 200:
				wallet_data = await walletJwt.json()
				JWT_TOKEN.append((wallet_data["RP"], int(time.time())))

				data = {
					"GAME_VERSION": "SET_CLIENT_GAME_VERSION_HERE__WITHOUT_V - https://prnt.sc/esaDdcJAX9H8",
					f"{ACCOUNT_ID}":
					{
						"JWT": JWT_TOKEN[0][0],
						"TIME": int(time.time()),
					}
				}
				with open(old_jwt_file, 'w') as f:
					json.dump(data, f, indent=4)


				if (debug_mode):
					print(f"» WALLET JWT: {wallet_data['RP']}")
				
				print("» PLEASE SET CLIENT GAME VERSION IN THE take_ab.json FILE!")
				input("")
				exit()

		# GET ACCESS TOKEN
		accessToken = await connection.request("GET", "/lol-rso-auth/v1/authorization/access-token")
		if accessToken.status == 200:
			accessToken_data = await accessToken.json()
			ACCESS_TOKEN = accessToken_data["token"]

			if (debug_mode):
				print(f"» ACCESS TOKEN: {accessToken_data['token']}")

#----------------------------------------------------------------#

async def buyChampion(connection):
	global LCU_PORT, GAME_VERSION, ACCOUNT_ID, CHAMP_TO_BUY, CURRENT_RP, CHAMP_TO_BUY

	if connection:
	# SET OWNED CHAMPIONS
		CO_LIST = []
		owned_champions = await connection.request("GET", "/lol-inventory/v2/inventory/CHAMPION")
		if owned_champions.status == 200:
			oc_data = await owned_champions.json()
			for obj in oc_data:
				if obj["ownershipType"] == "OWNED":
					CO_LIST.append(obj["itemId"])
			
			if (debug_mode):
				for champ in CO_LIST:
					print(f"» OWNED CHAMPION: {champ}")


	# SET CHAMPIONS POSSIBLE TO BUY
		CTB_LIST = []
		champions_to_buy = await connection.request("GET", "/lol-store/v1/catalog")
		if champions_to_buy.status == 200:
			ctb_data = await champions_to_buy.json()
			for obj in ctb_data:
				if obj["inventoryType"] == "CHAMPION":
					CTB_LIST.append((obj["itemId"], obj["prices"][1]["cost"]))

			if (debug_mode):
				for champ in CTB_LIST:
					print(f"» CHAMPION TO BUY: {champ[0]} | COST: {champ[1]}")

	# SET CHAMPION TO BUY
		CHAMP_TO_BUY = []
		champFound = False
		for item in CTB_LIST:
			if item[0] not in CO_LIST:
				if (((CURRENT_RP - item[1]) > 0) and (CURRENT_RP - item[1]) < 95) and (champFound == False):
					champFound = True
					CHAMP_TO_BUY.append((item[0], item[1]))
					print(f"» CHAMPION TO BUY: {item[0]} | COST: {item[1]}")

					if (debug_mode):
						print(f"C: {item[0]} | P: {item[1]}")

	# BUY CHAMPION
	if connection:
		champId, champPrice = CHAMP_TO_BUY[0]
		purchase_url = f'{STORE_URL}/storefront/v3/purchase?language=en_US'
		purchase_body = f'{{"accountId": {ACCOUNT_ID}, "items": [{{"inventoryType": "CHAMPION", "itemId": {champId}, "ipCost": null, "rpCost": {champPrice}, "quantity": 1}}]}}'
		purchase_header = {
		'Host': STORE_URL.replace("https://", ""),
		'Connection': 'keep-alive',
		'AUTHORIZATION': f'Bearer {ACCESS_TOKEN}',
		'Accept': 'application/json',
		'Accept-Language': 'en-US,en;q=0.9',
		'Content-Type': 'application/json',
		'Origin': f'https://127.0.0.1:{LCU_PORT}',
		'User-Agent': f'Mozilla/5.0 (Windows NT 6.2; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) LeagueOfLegendsClient/{GAME_VERSION} (CEF 91) Safari/537.36',
		'sec-ch-ua': '"Chromium";v"91"',
		'sec-ch-ua-mobile': '?0',
		'Sec-Fetch-Site': 'same-origin',
		'Sec-Fetch-Mode': 'no-cors',
		'Sec-Fetch-Dest': 'empty',
		'Referer': f'https://127.0.0.1:{LCU_PORT}',
		'Accept-Encoding': 'deflate, br',
		}
		
		purchase_response = requests.post(purchase_url, data=purchase_body, headers=purchase_header)
		if (debug_mode):
			print(purchase_response.text)

#----------------------------------------------------------------#

async def checkPurchaseTime(connection):
	global LCU_PORT, ACCESS_TOKEN, GAME_VERSION, STORE_URL
	if connection:
		# GET STORE HISTORY
		store_url = f'{STORE_URL}/storefront/v3/history/purchase?language=en_US'
		store_header = {
		'Host': STORE_URL.replace("https://", ""),
		'Connection': 'keep-alive',
		'AUTHORIZATION': f'Bearer {ACCESS_TOKEN}',
		'Accept': 'application/json',
		'Accept-Language': 'en-US,en;q=0.9',
		'Content-Type': 'application/json',
		'Origin': f'https://127.0.0.1:{LCU_PORT}',
		'User-Agent': f'Mozilla/5.0 (Windows NT 6.2; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) LeagueOfLegendsClient/{GAME_VERSION} (CEF 91) Safari/537.36',
		'sec-ch-ua': '"Chromium";v"91"',
		'sec-ch-ua-mobile': '?0',
		'Sec-Fetch-Site': 'same-origin',
		'Sec-Fetch-Mode': 'no-cors',
		'Sec-Fetch-Dest': 'empty',
		'Referer': f'https://127.0.0.1:{LCU_PORT}',
		'Accept-Encoding': 'deflate, br',
		}
		store_history = requests.get(store_url, headers=store_header)
		
		if (store_history.status_code == 200):
			sh_data = store_history.json()

			for obj in sh_data["transactions"]:
				if obj["inventoryType"] == "CHAMPION" and obj["refundable"] == True and obj["requiresToken"] == False:
					dPurchased = obj["datePurchased"]
					target_date = datetime.datetime.strptime(dPurchased, "%m/%d/%y")
					current_date = datetime.datetime.now().replace(hour=0, minute=0, second=0)
					if target_date.date() == current_date.date():
						next_day = current_date + datetime.timedelta(days=1)
						time_left = next_day - datetime.datetime.now()
						print(f"» [i] Time left for today's refundable purchase: {time_left}!")

						if (debug_mode):
							print(obj)
					else:
						print('''
						» [!] Token may have expired, please refund the purchased champion, then run boost!
						\n
						To avoid possible deductions from recently played games,
						please refund your character after entering champion select, then activate the boost!
						\n
						Within 5 seconds you'll be taken to the main menu, select Refund (3) and then Boost (1).
						''')
						time.sleep(5)
						await consoleUI(connection)
						#refundPurchase(connection)

async def refundPurchase(connection):
	global LCU_PORT, ACCESS_TOKEN, GAME_VERSION, STORE_URL
	if connection:
		# GET STORE HISTORY
		store_url = f'{STORE_URL}/storefront/v3/history/purchase?language=en_US'
		store_header = {
		'Host': STORE_URL.replace("https://", ""),
		'Connection': 'keep-alive',
		'AUTHORIZATION': f'Bearer {ACCESS_TOKEN}',
		'Accept': 'application/json',
		'Accept-Language': 'en-US,en;q=0.9',
		'Content-Type': 'application/json',
		'Origin': f'https://127.0.0.1:{LCU_PORT}',
		'User-Agent': f'Mozilla/5.0 (Windows NT 6.2; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) LeagueOfLegendsClient/{GAME_VERSION} (CEF 91) Safari/537.36',
		'sec-ch-ua': '"Chromium";v"91"',
		'sec-ch-ua-mobile': '?0',
		'Sec-Fetch-Site': 'same-origin',
		'Sec-Fetch-Mode': 'no-cors',
		'Sec-Fetch-Dest': 'empty',
		'Referer': f'https://127.0.0.1:{LCU_PORT}',
		'Accept-Encoding': 'deflate, br',
		}
		store_history = requests.get(store_url, headers=store_header)
		if (store_history.status_code == 200):
			shr_data = store_history.json()

			# REFUND CHAMPION
			rt = []
			rt_selected = False
			for obj in shr_data["transactions"]:
				if obj["inventoryType"] == "CHAMPION" and obj["refundable"] == True and obj["requiresToken"] == False and rt_selected == False:
					rt = obj

					refund_url = f'{STORE_URL}/storefront/v3/refund?language=en_US'
					refund_body = '{"accountId":' + str(ACCOUNT_ID) + ',"transactionId":"' + rt["transactionId"] + '","inventoryType":"CHAMPION","language":"en_US"}'
					refund = requests.post(refund_url, data=refund_body, headers=store_header)

					if (debug_mode):
						print(refund.text)
						print(rt)

#----------------------------------------------------------------#

async def buyBoost(connection):
	global JWT_TOKEN, LCU_PORT, LCU_PASSWORD

	if connection:
		requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

		boost_url = 'https://127.0.0.1:' + LCU_PORT + '/lol-login/v1/session/invoke?destination=lcdsServiceProxy&method=call&args=["","teambuilder-draft","activateBattleBoostV1","{\\"signedWalletJwt\\":\\"' + JWT_TOKEN[0][0] + '\\\"}"]'
		response = requests.post(boost_url, verify=False, auth=requests.auth.HTTPBasicAuth('riot', LCU_PASSWORD))
		if (debug_mode):
			print(f"» RESPONSE STATUS CODE: {response.status_code}")
			print(f"» RESPONSE TEXT: {response.text}")

		if response.status_code == 200:
			print("» [+] Lobby boost activated!")
			input("» Press ENTER if you want to go back... ")
			await consoleUI(connection)

#----------------------------------------------------------------#

async def consoleUI(connection):
	await getData(connection)
	await getStoreData(connection)

	introduction = '''
                    » » ----- » TAKE's ARAM BOOSTER « ----- « « 
\n
————————————————————————————————————————————————————————————————————————————————————
\n
» DISCORD: https://discord.gg/CmYZy4y6v5    <>    GITHUB: https://github.com/xTeJk «
\n
————————————————————————————————————————————————————————————————————————————————————
\n
| 1: Boost Lobby
| 2: Buy Champion
| 3: Refund Bought Champion
| 4: Exit Application
\n
| 0: Show Informations (LCU, Account, Store)
\n
'''
	print(introduction)

	user_input = input("» ")

	if user_input == "1":
		os.system('cls' if os.name == 'nt' else 'clear')
		boost_intro = '''
\n
————————————————————————————————————————————————————————————————————————————————————
If you're above 95 RP (boost cost), app will purchase the champion to lock you this value.
During next 24 hours you'll be able to boost ARAM lobbies an infinite number of times.
\n
Please note that champion purchased today must be refunded by the same time tomorrow at the latest.
Don't play with purchased champion, otherwise you won't be able to return it for free!
————————————————————————————————————————————————————————————————————————————————————
'''
		print(boost_intro)
		await checkPurchaseTime(connection)
		if CURRENT_RP < 95:
			print("» [!] Not enough RP to buy champion! (ignore if you've already bought one)")
		else:
			await buyChampion(connection)
		await buyBoost(connection)

	elif user_input == "2":
		os.system('cls' if os.name == 'nt' else 'clear')
		if CURRENT_RP < 95:
			print("» [!] Not enough RP to buy champion!")
		else:
			await buyChampion(connection)
		await consoleUI(connection)

	elif user_input == "3":
		os.system('cls' if os.name == 'nt' else 'clear')
		refund_intro = '''
\n
————————————————————————————————————————————————————————————————————————————————————
Remember to wait atleast 1 hour after playing last boosted lobby!
Otherwise, Riot is going to yoink your RP :(
\n
Don't play with bought champion, otherwise you won't be able to refund it for free!
————————————————————————————————————————————————————————————————————————————————————
'''
		print(f"{refund_intro}\nAre you sure you want to refund the latest purchase?")
		user_input_refund = input("» Y/N: ")
		if (user_input_refund == "Y" or user_input_refund == "y" or user_input_refund == "yes" or user_input_refund == "Yes" or user_input_refund == "YES" or user_input_refund == "ye" or user_input_refund == "Ye" or user_input_refund == "YE"):
			await refundPurchase(connection)
		else:
			await consoleUI(connection)


	elif user_input == "4":
		exit()

	elif user_input == "0":
		data_intro = f'''
\n
————————————————————————————————————————————————————————————————————————————————————
» LCU URL: https://127.0.0.1:{LCU_PORT}
» LCU Port: {LCU_PORT}
» LCU Password: {LCU_PASSWORD}
» Game Version: {GAME_VERSION}
\n
» Account ID: {ACCOUNT_ID}
» Current RP: {CURRENT_RP}
\n
» Store URL: {STORE_URL}
\n
'''
		print(data_intro)
		input("» Press ENTER if you want to go back... ")
		await consoleUI(connection)

#----------------------------------------------------------------#

if not IsLeagueRunning():
	print("» [!] League of Legends is not running!")
	input("")
	exit()

@connector.ready
async def main(connection):
	while True:
		await consoleUI(connection)

@connector.close
async def disconnect(connection):
	print("» LCU connection closed!")

connector.start()
