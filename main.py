from random_username.generate import generate_username
from random import randint
import json
from datetime import datetime
import requests
from configparser import ConfigParser

"""
Automated bot that demonstrates how the API of avasocial can be used.

The bot is not bound to main application and might be used standalone.
To evaluate the bot algorithm - set FAKE_API to True
In this case, instead of calling API of each operation - it will emulate the calls and use 'fake' data

the settings defined in settings.ini in the same folder as main.py

The complete flow description can be found in separate PDF.
Main steps:
- Sign-up new users
- Create random amount of posts (up to maximum) for each user
- Liking -  each user likes posts of other users until all posts are liked or the maximum amount of likes is reached
            for each user (i.e. no user is able to like)

"""


def print_info(text):
    """
    Helper for console printing with timestamp to avoid using logging module
    (since here it's unnecessary complication)
    :param text: text to print
    :return: None
    """
    _print("INFO", text)


def print_error(text):
    _print("ERROR", text)


def _print(status, text):
    print(f'{datetime.now().strftime("%d.%m.%y %H:%M:%S")} [{status}]: {text}')


class User:
    def __init__(self, bot, username):
        self.bot = bot
        self.username = username
        self.own_posts_with_likes = {}
        self.posts_liked = set()

        self.access_token = ''

    @property
    def posts_count(self):
        """
        :return: count of posts created by the user
        """
        return len(self.own_posts_with_likes.keys())

    def sign_up(self, password, email):
        """
        Sign-up the user in social network
        :param password:
        :param email:
        """
        if not self.bot.settings.fake_api:
            response = requests.post(url=self.bot.settings.base_url + "user/signup/",
                                     json={
                                         'user': {
                                             'username': self.username,
                                             'password': password
                                         },
                                         'email': email
                                     })
            if response.status_code != 200 or response.json().get('status') != 'success':
                raise Exception(response.json().get('message'))
        print_info(f'User {self.username} registered')

    def login(self):
        """
        Login user to allow making requests on behalf of the user
        After successful log in - updates property access_token of the user
        :return:
        """
        if self.bot.settings.fake_api:
            return

        response = requests.post(url=self.bot.settings.base_url + "user/login/",
                                 json={'username': self.username, 'password': self.bot.settings.password})
        self.access_token = response.json().get('access')

    @property
    def _headers(self):
        """
        :return: headers for request that requires log in
        """
        return {'Authorization': 'Bearer ' + self.access_token}

    def create_post(self, content):
        """
        Create post on behalf of the user. Requires self.login call beforehand
        :param content: content of the post
        :return: None
        """
        if self.bot.settings.fake_api:
            post_id = self.bot.post_id
            self.bot.post_id += 1
        else:
            response = requests.post(url=self.bot.settings.base_url + "post/create/",
                                     json={'content': content},
                                     headers=self._headers)

            post_id = response.json().get('message')

        print_info(f'User {self.username} posted (post ID: {post_id}) {content}')

        self.own_posts_with_likes[post_id] = 0

    def like_post(self, post_id):
        """
        User likes post with certain id. Requires self.login call beforehand
        :param post_id: ID of the post to like
        :return: None
        """
        if not self.bot.settings.fake_api:
            response = requests.get(url=self.bot.settings.base_url + f'post/{post_id}/like',
                                    headers=self._headers)
            if response.status_code != 200 or response.json().get('status') != 'success':
                print_error(f'Error liking post {post_id}: {response.json().get("message")}')
                return

        print_info(f'Post with ID {post_id} liked by user {self.username} successfully')
        self.posts_liked.add(post_id)

    def is_likeable(self, by_user=None):  # user can be liked if there is at least one post with 0 likes
        """
        Validates if the user can be liked by other user 'by_user' (every user can like one post once)
        if 'by_user' is None - validate if the user can be liked by anyone
        :param by_user: User to perform like
        :return: True if this user can be liked, False - otherwise
        """

        posts_liked = set() if by_user is None else by_user.posts_liked
        return 0 in [likes_cnt for post, likes_cnt in self.own_posts_with_likes.items() if post not in posts_liked]

    @property
    def random_post(self):
        """
        :return: ID of the random post created by the user
        """
        posts = [post_id for post_id in self.own_posts_with_likes.keys()]
        return posts[randint(0, len(posts) - 1)]

    def can_like(self, users):
        """
        Validates if the user can like anyone. I.e.:
        1. User didn't reach max amount of likes
        2. There are other users that this user can like
        :param users: all users
        :return: True if user can like someone, false - otherwise
        """
        if len(self.posts_liked) >= self.bot.settings.max_likes_per_user:
            return False

        return True in set((user.is_likeable(self) for user in users if user != self))

    def __eq__(self, other):
        return self.username == other.username


class Bot:
    class Settings:
        def __init__(self, ini_file):
            conf = ConfigParser()
            conf.read(ini_file)

            settings = conf['Settings']
            self.fake_api = settings.get('FAKE_API', '')
            self.base_url = settings.get('BASE_URL', '')
            self.password = settings.get('PASSWORD', '')
            self.email = settings.get('EMAIL', '')

            limits = conf['Limits']
            self.number_of_users = int(limits.get('number_of_users', '0'))
            self.max_posts_per_user = int(limits.get('max_posts_per_user', '0'))
            self.max_likes_per_user = int(limits.get('max_likes_per_user', '0'))

    def __init__(self, ini_file):
        self.settings = self.Settings(ini_file)

        # Since users of our social network are fancy about learning English
        # each their post will be a random English word definition from the dictionary

        try:
            with open('dictionary.json', 'r', errors='ignore') as file:
                dictionary = json.load(file)
                dictionary = [(key, value[0]) for key, value in dictionary.items()]
        except FileNotFoundError as e:
            raise FileNotFoundError('Bot requires dictionary.json with data') from e

        self.dictionary = dictionary

        self.post_id = 1  # used only for FAKE_API to imitate post IDs
        self.current_step = 1

        self.users = []

    @property
    def get_random_post_content(self):
        """
        Returns content for the post from dictionary.json
        :return: random content for the post.
        """
        entry = self.dictionary[randint(0, len(self.dictionary) - 1)]
        return f'{entry[0].capitalize()} - {entry[1]}'

    def is_posts_left(self):
        """
        Validates if there are posts with no likes left
        :return: True if there is at least one post to like, False - otherwise
        """
        return True in set((user.is_likeable() for user in self.users))

    def is_users_left(self):
        """
        Validates if there are users eligible to perform likes
        :return: True if there is at least one eligible user to like, False - otherwise
        """
        if len(self.users) < 2:
            return False
        return True in set((len(user.posts_liked) < self.settings.max_likes_per_user for user in self.users))

    def _print_step(self, text):
        print("-------------------------------------------------------------------------------------------------------")
        print_info(f'Step {self.current_step}: {text}')
        print("-------------------------------------------------------------------------------------------------------")
        self.current_step += 1

    def signup_users(self):
        """
        Registers users according to the number set in settings
        :return: None
        """
        self._print_step(f'Sign up {self.settings.number_of_users} users')
        for user in [User(self, username) for username in generate_username(self.settings.number_of_users)]:
            try:
                user.sign_up(self.settings.password, self.settings.email)
                self.users.append(user)
            except Exception as e:
                print_error(f'Username {user.username} skipped. Error: {str(e)}')

    def create_posts(self):
        """
        Creates random amount of posts (up to maximum value) for each registered user
        :return: None
        """
        self._print_step(
            f'Each user creates random number of posts (up to {self.settings.max_posts_per_user}) with any content')
        for user in self.users:
            user.login()
            for _ in range(randint(1, self.settings.max_posts_per_user)):
                user.create_post(self.get_random_post_content)

    def like_posts(self):
        """
        Performs liking activity according to the rules described in separate document
        Does liking until there are posts to like and there are users who can like
        :return: None
        """
        self._print_step('Start liking')

        # next user to perform a like is the user who has most posts and has not reached max likes
        # create queue sorted by number of posts per user
        users_queue = sorted(self.users, key=lambda _user: _user.posts_count, reverse=True)

        while True:  # like posts until:
            if not self.is_posts_left():  # 1. there is no posts with 0 likes
                print_info('All posts are liked at least once. Stop bot')
                break

            if not self.is_users_left():  # 2. there are available users to like
                print_info('No more users able to like. Stop bot')
                break

            # user performs “like” activity until he reaches max likes (and there are someone left to like)
            for user in users_queue:
                user.login()
                while user.can_like(self.users):
                    for user_to_like in self.users:
                        if user_to_like == user or not user_to_like.is_likeable(user):
                            continue  # do not like their own posts or users without posts with no likes

                        post_to_like = user_to_like.random_post
                        if post_to_like in user.posts_liked:  # can't like same post twice
                            continue

                        user_to_like.own_posts_with_likes[post_to_like] += 1
                        user.like_post(post_to_like)

    def print_results(self):
        print('----------------------')
        print("Total results:")
        print("Users created: ", len(self.users))
        print("Details: ")
        for user in self.users:
            print("Username: ", user.username)
            print("Own posts (post_id, number of likes): ", user.own_posts_with_likes)
            print()


def main():
    bot = Bot('settings.ini')

    bot.signup_users()
    bot.create_posts()
    bot.like_posts()
    bot.print_results()


if __name__ == '__main__':
    main()
