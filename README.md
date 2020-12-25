# avabot
Command-line bot that demonstrates how https://github.com/Luckykarter/avasocial works 

The bot is not bound to avasocial and utilizes only externally exposed endpoints of the social network.
It also can be used without connecting to real API for pure testing of the bot scripts without bothering a server if *FAKE_API* is set to non-empty in **settings.ini**.

## Components
### main.py
The main script to be executed in command line. It prints its results in console output.
The scenario includes the following steps:

- Sign-up new users according to amount of users given in **settings.ini**
- Create random amount of posts (up to maximum) for each user
- Liking - each user likes posts of other users until all posts are liked or the maximum amount of likes is reached for each user (i.e. no user is able to like)


### settings.ini
This file is required for the app to operate.
The description of each setting can be found in inline comments of the file

### dictionary.json
This file supplies the content for posts that are created by users. 

Current file is an English dictionary. Since the users created by the bot are fancy about learning English -
each their post will be a random English word definition from the dictionary.

### Used libraries
- requests - for API communication with the social network via REST API
- random-username - for generating fancy random usernames for newly created users
