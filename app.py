#!/usr/bin/python
#
# BetVictor Technical Task
#
# app.py
# Application that monitors canary release
# 1. Listens for "release" and "error" messages:
# 	- Release:
#		- There is a new AMI in the release ASG
#		- Set DNS weights: 200 : 54
# 	- Error:
#		- Something wen't wrong, stop release
#		- Set DNS weights: 254 : 0
#		- Send SNS/email to admin
#
# Amazon SNS message:
# POST / HTTP/1.1
# x-amz-sns-message-type: Notification
# x-amz-sns-message-id: 22b80b92-fdea-4c2c-8f9d-bdfb0c7bf324
# x-amz-sns-topic-arn: arn:aws:sns:us-west-2:123456789012:MyTopic
# x-amz-sns-subscription-arn: arn:aws:sns:us-west-2:123456789012:MyTopic:c9135db0-26c4-47ec-8998-413945fb5a96
# Content-Length: 773
# Content-Type: text/plain; charset=UTF-8
# Host: example.com
# Connection: Keep-Alive
# User-Agent: Amazon Simple Notification Service Agent
#
# {
#   "Type" : "Notification",
#   "MessageId" : "22b80b92-fdea-4c2c-8f9d-bdfb0c7bf324",
#   "TopicArn" : "arn:aws:sns:us-west-2:123456789012:MyTopic",
#   "Subject" : "SNS-TOPIC",
#   "Message" : "RELEASE | ERROR",
#   "Timestamp" : "2012-05-02T00:54:06.655Z",
#   "SignatureVersion" : "1",
#   "Signature" : "EXAMPLEw6JRNwm1LFQL4ICB0bnXrdB8ClRMTQFGBqwLpGbM78tJ4etTwC5zU7O3tS6tGpey3ejedNdOJ+1fkIp9F2/LmNVKb5aFlYq+9rk9ZiPph5YlLmWsDcyC5T+Sy9/umic5S0UQc2PEtgdpVBahwNOdMW4JPwk0kAJJztnc=",
#   "SigningCertURL" : "https://sns.us-west-2.amazonaws.com/SimpleNotificationService-f3ecfb7224c7233fe7bb5f59f96de52f.pem",
#   "UnsubscribeURL" : "https://sns.us-west-2.amazonaws.com/?Action=Unsubscribe&SubscriptionArn=arn:aws:sns:us-west-2:123456789012:MyTopic:c9135db0-26c4-47ec-8998-413945fb5a96"
#   }
import boto.sns as sns
import json
from flask import Flask, request, jsonify
########
# USER #
########
# TODO:
# Get this from environment
ACCESS = '<REPLACE_WITH_ACCESS_KEY_ID>'
SECRET = '<REPLACE_WITH_SECRET_ACCESS_KEY>'

# defines the step to use for release updates
step=32
############
# USER END #
############

#Init Flask
app = Flask(__name__)

# GLOBAL
config={"dns_stable":"https://",
		"dns_release": "https://",
		"sns_stable": "",
		"sns_release": "",
		"limit_upper": 250,
		"limit_lower": 10,
		"step": 32
		}

# TODO:
# Add a proper mutex
IN_PROGRESS=False

# STATIC
APP_DEBUG=True

# FUNCTIONS
# description: 
# arguments:
# return
def sns_subscribe(sns_name):
	return True
def sns_unsubscribe(sns_name):
	return True

def route53_set_weight(dns_name, weight):
	return True

def route53_get_weight(dns_name):
	return 255

def route53_adjust_weight(dns_name, increment):
	current_weight=route53_get_weight(dns_name)
	current_weight=(current_weight + increment)
	if current_weight > 255:
		current_weight=255
	elif current_weight < 0:
		current_weight=0
	result=route53_set_weight(dns_name, current_weight)
	return result

def system_output(msg):
	print "%s %s" % (str(datetime.datetime.now()), msg)

def release_revert():
	return True

def release_cancel(msg):
	# global IN_PROGESS config
	IN_PROGESS=False
	# config["dns_stable"]="https://"
	# config["dns_release"]="https://"
	return jsonify('{"status":"error", "message": "%s"' % msg )

# description: Processes requests for new release
# arguments: stable - dns of stable elb
#			 release - dns of release elb
# return: JSON-object:
# Success if the release is initiated
# Error otherwise
@app.route('/release')
def release():
	# global IN_PROGESS config
	# Check if already in progress
	if IN_PROGRESS:
		return release_cancel("Release already in progress. Try the /query endpoint for more information")
	IN_PROGRESS=TRUE

	# Get the data
	msg=json.loads(request.json)
	# Check for fields
	if not msg["dns_stable"]:
		return release_cancel("Missing DNS information for stable environment: dns_stable")
	elif not msg["dns_release"]:
		return release_cancel("Missing DNS information for release environment: dns_release ")
	elif not msg["sns_stable"]:
		return release_cancel("Missing SNS information for stable environment: sns_stable ")
	elif not msg["sns_release"]:
		return release_cancel("Missing SNS information for release environment: sns_release ")

	# Set global
	config["dns_stable"]=msg["dns_stable"]
	config["dns_release"]=msg["dns_release"]
	config["sns_stable"]=msg["sns_stable"]
	config["sns_release"]=msg["sns_release"]

	# Subscribe to SNS Topic
	if not (sns_subscribe(config["sns_release"])):
		return release_cancel("Could not register to SNS Topic")
	# return success
	return jsonify('{"status": "success", "message": "Initiated new release"}')

# description: Processes SNS message 
# arguments: sns-message
# return: JSON
# {"status" : "ok"}
@app.route('/sns-topic')
def sns_process():
	# check for header
	msg=json.loads(request.json())
	# verify the sns
	# Check message and adjust state
	if msg["Message"].startswith("success"):
		route53_adjust_weight(config["dns_release"], step)
		route53_adjust_weight(config["dns_stable"], -step)
	elif msg["Message"].startswith("failure"):
		route53_adjust_weight(config["dns_release"],-step)
		route53_adjust_weight(config["dns_stable"], step)
	else:
		# other type of message?
		return jsonify('{"status": "error", "message": "not in success/failure scenario"')

	# Check if weight is in upper/lower limits
	if route53_get_weight(config["dns_release"]) >= config["limit_upper"]:
		# Release is success
		sns_unsubscribe(config["sns_release"])		
		# Set the weights to fully route to release
		route53_set_weight(config["dns_release"], 255)
		route53_set_weight(config["dns_stable"], 0)
		# Msg admin to let him know to finalize the release
		msg_admin("Release application: Success", "Success in releasing to %s" % config["dns_release"])
		# Set IN_PROGRESS flag
		IN_PROGESS=False
	elif route53_get_weight(config["dns_release"]) <= config["limit_lower"]:
		# Release failed
		sns_unsubscribe(config["sns_release"])
		# Set the weights to fully route to stable
		route53_set_weight(config["dns_stable"], 255)
		route53_set_weight(config["dns_release"], 0)
		# Msg admin 
		msg_admin("Release application: Error in release","Error in release, Reverting")
		# Set IN_PROGRESS flag
		IN_PROGESS=False
	return jsonify('{"status": "ok"}')
	
# description: checks the current weights 
# arguments: none
# return: JSON Object:
# {
#	"status": "in_progress",
#	"weight_stable": <weight>,
#	"weight_release": <weight> 
# }
@app.route('/query')
def release_progress():
	if IN_PROGESS:
		return """{
				"status": "release_in_progress",
				"weight_stable": "%s",
				"weight_release": "%s"
		}""" % (route53_get_weight(config["dns_stable"]), route53_get_weight(config["dns_release"]))
	
	else:
		return """{
			"status": "stable_operation"
		}"""

# MAIN
if __name__ == '__main__':
  app.run(debug=APP_DEBUG)

# check message
# msg="""
# {
#   "Type" : "Notification",
#   "MessageId" : "22b80b92-fdea-4c2c-8f9d-bdfb0c7bf324",
#   "TopicArn" : "arn:aws:sns:us-west-2:123456789012:MyTopic",
#   "Subject" : "SNS-TOPIC",
#   "Message" : "RELEASE",
#   "Timestamp" : "2012-05-02T00:54:06.655Z",
#   "SignatureVersion" : "1",
#   "Signature" : "EXAMPLEw6JRNwm1LFQL4ICB0bnXrdB8ClRMTQFGBqwLpGbM78tJ4etTwC5zU7O3tS6tGpey3ejedNdOJ+1fkIp9F2/LmNVKb5aFlYq+9rk9ZiPph5YlLmWsDcyC5T+Sy9/umic5S0UQc2PEtgdpVBahwNOdMW4JPwk0kAJJztnc=",
#   "SigningCertURL" : "https://sns.us-west-2.amazonaws.com/SimpleNotificationService-f3ecfb7224c7233fe7bb5f59f96de52f.pem",
#   "UnsubscribeURL" : "https://sns.us-west-2.amazonaws.com/?Action=Unsubscribe&SubscriptionArn=arn:aws:sns:us-west-2:123456789012:MyTopic:c9135db0-26c4-47ec-8998-413945fb5a96"
#   }
# """
# msg=json.loads(msg)

# print msg
# if RELEASE
#	DNS set -step:+step
# elif ERROR
#	DNS set +step:-step

# endpoint release
#	- IN_PROGESS=True
#	- Set DNSDOMAIN_STABLE
#	- Set DNSDOMAIN_RELEASE
#	- Subscribe to Topic

# endpoint sns
#	- If error in release asg
#	- abort release | set more weight to stable
#