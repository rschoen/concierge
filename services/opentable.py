import json
import logging
import os
import pathlib
import time
from datetime import datetime
from os.path import exists
import requests
from dateutil.parser import parse

class OpentableService:
	def login(self,config):
		self.bearer_token = config["bearer_token"]
		self.phone = config["phone"]
		self.email = config["email"]
		self.first_name = config["first_name"]
		self.last_name = config["last_name"]
		#self.diner_id = config["diner_id"]
		self.headers = {
			'Content-Type': 'application/json',
			'Authorization': f"Bearer {self.bearer_token}",
			'User-Agent': 'com.context optional.OpenTable/15.2.0.16; iPhone; iOS/15.1.1; 3.0;',
		}
		self.unauth_headers = {
			'Content-Type': 'application/json',
			'Authorization': 'undefined',
			'X-Csrf-Token': '1',
			'User-Agent': 'com.context optional.OpenTable/15.2.0.16; iPhone; iOS/15.1.1; 3.0;',
		}
		self.cookies = {'OT-Session-Update-Date': str(int(time.time()))}
		return True

	def get_availability_for_restaurant_id(self,id,date,diners):
		data = {
			"forceNextAvailable": "true",
			"includeNextAvailable": True,
			"availabilityToken": "eyJ2IjoyLCJtIjoxLCJwIjoxLCJzIjowLCJuIjowfQ",
			"dateTime": date,
			"requestTicket": "true",
			"allowPop": True,
			"attribution": {
				"partnerId": "84"
			},
			"partySize": diners,
			"includeOffers": True,
			"requestPremium": "true",
			"requestDateMessages": True,
			"rids": [
				str(id)
			],
			"requestAttributeTables": "true"
		}

		data = {
			"rid": str(id),
			"dateTime": date,
			"partySize": diners,
			"enableFutureAvailability": True
		}

		response = requests.post('https://www.opentable.com/restref/api/availability?lang=en-US', headers=self.headers,
								cookies=self.cookies,
								data=json.dumps(data))
		return response.json()


	def make_reservation_for_slot_response(self,venue,slot,diners):
		slot_time = slot['dateTime']
		slot_hash = slot['slotHash']
		data = {
			"partySize": diners,
			"dateTime": slot_time,
			"seatingOption": "default",
			"reservationType":"Standard",
			"slotHash": slot_hash,
			"rid": venue
		}
		logging.info(f"Attempting to lock down reservation {slot_hash} at {slot_time}")
		response = requests.post(f'https://www.opentable.com/restref/api/slot-lock',
								 headers=self.headers, cookies=self.cookies,

								 data=json.dumps(data))
		lock = response.json()

		lock_id = lock['slotLockId']
		logging.info(f"Successfully locked reservation with lock id {lock_id}")
		complete_reservation_data = {
			"restaurantId": venue,
			"partySize": diners,
			"reservationDateTime": slot_time,
			"slotHash": slot_hash,
			"slotLockId": lock_id,
			"slotAvailabilityToken": slot['slotAvailabilityToken'],
			"reservationType": "Standard",
			"reservationAttribute": "default",
			"correlationId": "asdf",
			"country": "US",
			"phoneNumber": str(self.phone),
			"restaurantNotes": "",
			"firstName": self.first_name,
			"lastName": self.last_name,
			"katakanaFirstName": "",
			"katakanaLastName": "",
			"email": self.email,
			"phoneNumberCountryId": "US",
			"occasion": "default",
			"optInSmsNotifications": False,
			"optInEmailRestaurant": False,
			"isRestRef": True,
			"pointsType": "None"
		}
		logging.info(f"Attempting to complete reservation {lock_id}")
		final_booking_response = requests.post(
			f"https://www.opentable.com/dapi/booking/make-reservation?lang=en-US&ot_source=Restaurant%20website", cookies=self.cookies,
			headers=self.unauth_headers,
			data=json.dumps(complete_reservation_data))

		# This will return not JSON if it fails, although sometimes when it fails it actually makes the reservation
		# We'll write this for the happy path, but welcome PRs cleaning this up
		final_booking_data = final_booking_response.json()

		if 'reservationId' in final_booking_data:
			res_time = str(parse(slot_time).hour) + ":" + str(parse(slot_time).minute)
			print(f"Successfully made reservation {final_booking_data['reservationId']} at {res_time}")
			return res_time
		else:
			return None


	def try_to_reserve(self,venue,date,diners,earliest_hour,latest_hour):
		#try:
			res_time = str(date)+f"T{earliest_hour}:00"
			availability_response = self.get_availability_for_restaurant_id(venue,res_time,diners)
			if 'availability' in availability_response:
				for day in availability_response['availability']:
					day_data = availability_response['availability'][day]
					if 'timeSlots' in day_data and len(day_data['timeSlots']):
						for slot in day_data['timeSlots']:
							slot_date = parse(slot['dateTime'])
							# todo - sort available dates by order of preference. if a big batch gets released and you have
							# 5pm to 11pm selected, you might get the 5pm even though the 8pm is preferable
							if slot_date.hour >= earliest_hour and slot_date.hour <= latest_hour:  # and slot_date.day >= MIN_DATE:
								logging.warning(f"Found available time slot on {slot['dateTime']}")
								self.make_reservation_for_slot_response(venue,slot,diners)
								return
				print("No availability found")
			else:
				print("Error with response, unknown format")
		#except Exception as e:
		#	print(e)
		#	pass
