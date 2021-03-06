# Simple user model that we can use
# in further development of pm part
#
# Some helpful static methods added
#
#
# VALIDATORS
#
# valid_password()
# valid_username()
# valid_email()
# valid() - check all above
#
#
# SAVE
# 
# save() - save and return user if valid() else False
#
#
# LOG TOKEN
#
# bcrypt.gensalt() is used for creating tokens
# tokens in database are hashed with bcrypt
# new token is generated with every new login


from google.appengine.ext import  ndb
from google.appengine.ext.ndb.key import Key
from externals.bcrypt import bcrypt as bc
from Message import Message, Conversation

import re

_UNAMEP = r'^[A-Za-z0-9_-]{4,21}$'
uname = re.compile(_UNAMEP)


class ExternalProfileLink(ndb.Model):
    url             = ndb.StringProperty(required=True)
    profile_loc     = ndb.StringProperty(required=True, choices={'Facebook', 'Twitter', 'G+',
                                                                'LinkedIn', 'Website', 'GitHub', 'BitBucket',
                                                                'Blog', 'Portfolio', 'Other', 'Coursera', })

class Location(ndb.Model):
    city            = ndb.StringProperty()
    country         = ndb.StringProperty()


class User(ndb.Model):
    username        = ndb.StringProperty(required=True)
    username_norm   = ndb.ComputedProperty(lambda self: self.username.lower())
    password        = ndb.StringProperty(required=True)
    email           = ndb.StringProperty(required=True)

    created         = ndb.DateTimeProperty(auto_now_add=True)
    updated         = ndb.DateTimeProperty(auto_now=True)

#    friends         = ndb.KeyProperty(kind='User', repeated=True)
    friends         = ndb.StringProperty(repeated=True)

    # details
    forum_name      = ndb.StringProperty()
    real_name       = ndb.StringProperty()
    short_about     = ndb.StringProperty()
    tools           = ndb.TextProperty()
    age             = ndb.IntegerProperty()
    profile_link    = ndb.StructuredProperty(ExternalProfileLink, repeated=True)
    location        = ndb.StructuredProperty(Location)

    # TODO: upload to a static directory?
    avatar          = ndb.BlobProperty()
    avatar_url      = ndb.StringProperty(default="/img/defaultavatar.png")
    use_gravatar    = ndb.BooleanProperty(default=False)

    # settings
    show_friends    = ndb.BooleanProperty(default=False)
    log_token       = ndb.StringProperty(required=False)
    notify_on_msg   = ndb.BooleanProperty(default=True)

    conversations   = ndb.KeyProperty(kind='Conversation', repeated=True)


    def add_conversation(self, conversation):
        self.conversations.append(conversation)

    def get_all_conversations(self):
        return ndb.get_multi(self.conversations)

    @classmethod
    def add_conversation_for_user(cls, username, conversation):
        """Add a conversation thread for user with username
        """
        u = cls.query(User.username_norm == username.lower()).get()
        if u:
            u.conversations.append(conversation)
            u.put()
            return u
        return None

    @classmethod
    def add_conversation_for_users(cls, conversation, *users):
        """Adds participants to a conversation thread for each user in users
        """
        if all(users):
            users = [users[0]]
        for user in users:
            cls.add_conversation_for_user(user, conversation)

    @classmethod
    def get_user(cls, username):
        """Get a User object given username

        Returns:
         A User class instance
        """
        key = ndb.Key(User, username.lower())
        u = key.get()
        return u

    @classmethod
    def get_conversations_for(cls, username, offset, limit):
        """Gets conversations for user with username

        Returns:
         A list of Conversation objects for username
        """
        limit = int(limit) if limit else 10
        offset = int(offset) if offset else 0

        c = Conversation.query(Conversation.receivers_list_norm.IN([username.lower()]))\
                        .order(-Conversation.modified)\
                        .fetch(limit=limit, offset=offset, keys_only=True)
        return ndb.get_multi(c)

    @classmethod
    def valid_password(cls, password):
        p = len(password)
        return  p >= 8 and p < 50

    @classmethod
    def valid_username(cls, username):
        if uname.match(username):
            users = cls.query(User.username_norm == username.lower()).fetch(1, projection=['username'])
        else:
            return False

        return not users

    @classmethod
    def valid_email(cls, email):
        email = cls.query(User.email == email).fetch(1, projection=['username'])
        return not email

    @classmethod
    def valid(cls, username, email, password):
        return cls.valid_password(password) and \
               cls.valid_username(username) and \
               cls.valid_email(email)

    @classmethod
    def save(cls, username, email, password):
        """Save a user object

        Returns:
         The saved User object
        """
        if cls.valid(username, email, password):
            password = bc.hashpw(password, bc.gensalt())
            # call to create and save log token is in signup controller
            user = cls(id = username, username = username, password = password, email = email)
            user.put()
            return user
        return False

    @classmethod
    def add_friend(cls, me, friend):
        #TODO: check if friend exists, etc
        #TODO: friend requests/approvals - right now auto adds to both parties
        #TODO: use transactions

        mes = cls.query(cls.username_norm == me.lower()).get()
        if friend not in mes.friends:
            mes.friends.append(friend.lower())
            mes.put()

        # just auto add me to the other person's list
        fs = cls.query(cls.username_norm == friend.lower()).get()
        if me not in fs.friends:
            fs.friends.append(me.lower())

            fs.put()

    def get_friends(self, limit=10, offset=0):
        """Gets friends for current User object

        Returns:
         A list of User objects who are current in current User's friends list or
         None if User's friends list is empty
        """
        if bool(self.friends):
            f = User.query(User.username_norm.IN(self.friends)).order(-User.username)\
                    .fetch(limit, offset=offset, projection=['username', 'real_name'])
            return f
        return None

    def delete_friend(self):
        #TODO: deleting friends
        pass

    def get_conversations(self, limit=10, offset=0):
        """UNUSED - Get conversations for current User object

        Returns:
         A list of Conversation objects
        """

        c = Conversation.query(self.username_norm in Conversation.receivers, keys_only=True)\
                        .order(Conversation.modified)\
                        .limit(limit, offset=offset)
        return ndb.get_multi(c)

    @classmethod
    def add_new_conversation(cls, sender, receiver, title, content):
        """Adds new conversation with receiver for sender, returns Conversation object
        """
        #TODO: check if sender and receiver aren't the same person, if so, add only once

        skey = ndb.Key('User', sender)
        rkey = ndb.Key('User', receiver)

        if sender == receiver:
            rl = [skey]
            rln  = [sender]
        else:
            rl = [rkey, skey]
            rln = [sender, receiver]

        conv = Conversation(
            owner = sender,
            receivers_list = rl,
            receivers_list_norm = rln,
            title = title,
        )
        msg = Message(
            sender = sender,
            content = content
        )


        k = msg.put()
        conv.insert_message(k)
        ck = conv.put()

        User.add_conversation_for_users(ck, sender, receiver)

        return conv, msg
