import requests
import math
import datetime

headers = {
	 'origin': 'https://resy.com',
	 'accept-encoding': 'gzip, deflate, br',
	 'x-origin': 'https://resy.com',
	 'accept-language': 'en-US,en;q=0.9',
	 'authorization': 'ResyAPI api_key="VbWk7s3L4KiK5fzlO7JD3Q5EYolJI7n5"',
	 'content-type': 'application/x-www-form-urlencoded',
	 'accept': 'application/json, text/plain, */*',
	 'referer': 'https://resy.com/',
	 'authority': 'api.resy.com',
	 'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/70.0.3538.102 Safari/537.36',
}


class ResyService:
	def login(self,config):
		data = {'email': config["username"], 'password': config["password"]}
		response = requests.post('https://api.resy.com/3/auth/password', headers=headers, data=data)
		res_data = response.json()
		if 'em_address' not in res_data or res_data['em_address'] != config["username"]:
			return False

		self.auth_token = res_data['token']
		self.payment_method_string = '{"id":' + str(res_data['payment_method_id']) + '}'
		return True

	def try_to_reserve(self,venue,date,diners,earliest_hour,latest_hour):
		print("Checking for reservations at "+str(venue)+" on "+date.isoformat()+" for "+str(diners))
		best_time = math.floor((earliest_hour + latest_hour)/2.0)
		best_table = self.find_table(date,diners,best_time,venue)
	
		if best_table is not None:
			hour = datetime.datetime.strptime(best_table['date']['start'],"%Y-%m-%d %H:%M:00").hour
			if (hour >= earliest_hour) and (hour <= latest_hour):
				config_id = best_table['config']['token']
				self.make_reservation(config_id,date,diners)
				return hour
			else:
				return None
		else:
			return None


	def find_table(self,res_date,party_size,table_time,venue_id):
	#convert datetime to string
		day = res_date.strftime('%Y-%m-%d')
		params = (
		 ('x-resy-auth-token', self.auth_token),
		 ('day', day),
		 ('lat', '0'),
		 ('long', '0'),
		 ('party_size', str(party_size)),
		 ('venue_id',str(venue_id)),
		)
		response = requests.get('https://api.resy.com/4/find', headers=headers, params=params)
		data = response.json()
		results = data['results']
		if len(results['venues']) > 0:
			open_slots = results['venues'][0]['slots']
			if len(open_slots) > 0:
				available_times = [(k['date']['start'],datetime.datetime.strptime(k['date']['start'],"%Y-%m-%d %H:%M:00").hour) for k in open_slots]
				closest_time = min(available_times, key=lambda x:abs(x[1]-table_time))[0]

				best_table = [k for k in open_slots if k['date']['start'] == closest_time][0]

				return best_table

	def make_reservation(self,config_id,res_date,party_size):
		print("Making the reservation now!")
		#convert datetime to string
		day = res_date.strftime('%Y-%m-%d')
		party_size = str(party_size)
		params = (
			 ('x-resy-auth-token', self.auth_token),
			 ('config_id', str(config_id)),
			 ('day', day),
			 ('party_size', str(party_size)),
		)
		details_request = requests.get('https://api.resy.com/3/details', headers=headers, params=params)
		details = details_request.json()
		book_token = details['book_token']['value']
		headers['x-resy-auth-token'] = self.auth_token
		data = {
		  'book_token': book_token,
		  'struct_payment_method': self.payment_method_string,
		  'source_id': 'resy.com-venue-details'
		}
		response = requests.post('https://api.resy.com/3/book', headers=headers, data=data)
		responseJSON = response.json()
		print(responseJSON)

		resID = 0
		if "reservation_id" in responseJSON:
			resID = responseJSON["reservation_id"]
		elif "specs" in responseJSON and "reservation_id" in responseJSON["specs"]:
			resID = responseJSON["specs"]["reservation_id"]

		if resID > 0:
			print("Successfully got reservation ID " + str(resID))
		else:
			print("Looks like reservation failed. Sad :(")
