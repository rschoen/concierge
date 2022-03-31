import yaml
import datetime
from math import floor
import random
import time

config_file = "config.yaml"
venue_file = "venues.yaml"

from services import resy, opentable, tock
valid_services = {"resy": resy.ResyService, "opentable": opentable.OpentableService, "tock": tock.TockService}


def read_config(file):
	config = None
	with open(file, "r") as stream:
		try:
			config = yaml.safe_load(stream)
		except yaml.YAMLError as exc:
			print("Error loading configuration file " + file)
			print(exc)
			quit()

	validate_config(config)
	return config

def validate_config(config):
	try:
		assert config["diners"] > 0, "You must have at least 1 diner."
		assert config["diners"] <= 10, "You can have at most 10 diners."
		assert config["check interval minutes"] >= 5, "You can check for reservations at most every 5 minutes."
		assert config["interval fudge factor"] >= 0, "Interval fudge factor must be 0 or greater."
		assert config["interval fudge factor"] <= 1, "Interval fudge factor can be at most 1.0."
		assert len(config["venues"]) > 0, "You must include at least one venue."
		assert len(config["dates"]) > 0, "You must include at least one date."
		assert config["earliest start hour"] >= 0, "Earliest start hour must be at least 0."
		assert config["earliest start hour"] <= 23, "Earliest start hour must be at most 23."
		assert config["latest start hour"] >= 0, "Latest start hour must be at least 0."
		assert config["latest start hour"] <= 23," Latest start hour must be at most 23."
		assert config["earliest start hour"] <= config["latest start hour"], "Earlest start hour cannot be after latest start hour." 
		assert len(config["services"]) > 0, "You must include at least one reservation service."

		any_service_enabled = False
		for service in config["services"]:
			if config["services"][service]["enabled"] == True:
				assert service in valid_services, "Not a supported service: "+service+". Valid services are "+valid_services
				any_service_enabled = True
		assert any_service_enabled == True, "You must enable at least one reservation service."
	except AssertionError as msg:
		print("Invalid configuration file.")
		print(msg)
		quit()

def initialize_services(services):

	service_objects = {}
	for service_name in services:

		if services[service_name]["enabled"] == False:
			continue

		service_obj = valid_services[service_name]()
		if service_obj.login(services[service_name]):
			print("Successfully logged in to "+service_name)
			service_objects[service_name] = service_obj
		else:
			print("Failed to log in to "+service_name+".")
	return service_objects

def load_venues(venue_file,chosen_venues,enabled_services):
	venues = None
	with open(venue_file, "r") as stream:
		try:
			venues = yaml.safe_load(stream)
		except yaml.YAMLError as exc:
			print("Error loading venues file " + venue_file)
			print(exc)
			quit()

	service_mappings = {}
	for chosen_venue in chosen_venues:
		found = False
		for service in venues:
			if found:
				break
			if service not in enabled_services:
				continue
			for venue in venues[service]:
				if venue.lower() == chosen_venue.lower():
					service_mappings[chosen_venue] = {"service": service, "venue_id": venues[service][venue]}
					found = True
					break
		if not found:
			print("Failed to find venue '" + chosen_venue + "' among enabled services. Skipping.")

	if len(service_mappings) < 1:
		print("Failed to find any venues among matching services.")
		print("You may need to add the venues to " + venue_file + " or enable more services.")
		quit()

	return service_mappings

def format_dates(dates):
	date_objects = []
	for date in dates:
		if type(date) == datetime.date:
			date_objects.append(date)
		else:
			print("Date "+date+" doesn't seem to be in YYYY-MM-DD format. Skipping.")
	return date_objects

def sleep_random(sleep_minutes,fudge):
	sleep_seconds = sleep_minutes*60
	fudge_percent = 2*fudge*random.random()-fudge
	sleep_seconds = int(sleep_seconds * (1+fudge_percent))
	sleep_minutes = floor(sleep_seconds/60)
	sleep_remainder = sleep_seconds-sleep_minutes*60

	print("Sleeping for " + str(sleep_minutes) + " minutes, "+ str(sleep_remainder) + " seconds...")
	time.sleep(sleep_seconds)


def main():
	config = read_config(config_file);
	enabled_services = [service for service in config["services"] if config["services"][service]["enabled"] == True]
	service_mappings = load_venues(venue_file,config["venues"],enabled_services)
	services = initialize_services(config["services"])
	dates = format_dates(config["dates"])


	
	while True:
		for date in dates:
			reserved = False
			if date < datetime.date.today():
				print ("Date "+date.isoformat()+" is in the past. Skipping from now on.")
				dates.remove(date)
				continue
			for venue in service_mappings:
				venue_id = service_mappings[venue]["venue_id"]

				reservation_time = None

				#try:
				reservation_time = services[service_mappings[venue]["service"]].try_to_reserve(venue_id,date,config["diners"],config["earliest start hour"],config["latest start hour"])
				#except Exception as e:
				#	print("Unexpected error making reservation: "+str(e))

				if reservation_time != None:
					print("Successfully reserved "+venue+" on "+date.isoformat()+" at "+str(reservation_time)+" for "+str(config["diners"])+" diners.")
					print("No longer attempting to reserve on that date, or at that venue.")
					del service_mappings[venue]
					dates.remove(date)
					reserved = True
					break

		if len(dates) < 1:
			print("No dates left to book. Shutting down!")
			quit()

		if len(service_mappings) < 1:
			print ("No venues left to book. Shutting down!")
			quit()

		sleep_random(config["check interval minutes"],config["interval fudge factor"])


main()
