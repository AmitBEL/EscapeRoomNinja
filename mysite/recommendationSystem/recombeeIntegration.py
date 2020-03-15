from datetime import datetime, timedelta
import json

from recombee_api_client.api_client import RecombeeClient
from recombee_api_client.api_requests import *

from core.models import Room, User
from core import serializers

# constants

API_KEY = "overrided_by_local_settings"
DB_NAME = "escape-ninja-dev"  # TODO maybe use prod and dev separately
RECOMMENDATION_SIZE = 10
NOT_DONE = -100
RECOMMENDATION_BOOSTER = "if 'totalRating' <= 2 then 0.2 else " \
                         "(if 'totalRating' <= 5 then 0.5 else " \
                         "(if 'totalRating' <= 8 then 0.8 else 1.1))"


# deserializing a JSON into a dictionary
# params:
# serialized_JSON - the JSON to convert to a dictionary
# return - a dictionary representation of the JSON given
def serialized_json_to_dict(seriazlized_JSON):
    try:
        print("details are:", seriazlized_JSON)
        # room_details = json.loads(seriazlized_JSON)[0]
        room_details = seriazlized_JSON
        return room_details
    except:
        raise Exception("bad room JSON was given! could not deserialize room json!")
        return


# returning a new room JSON which consists only of relevant field for recombee
# params:
# room_serial - the JSON to extract information from
# return - a new JSON with relevant values
def serialized_room_to_relevant_info_serial(room_serial):
    room_details = serialized_json_to_dict(room_serial)
    return {"name": room_details['name'],
            "totalRating": str(room_details['totalRating']),
            "scary_rank": str(room_details['scary_rank']),
            "difficulty_rank": str(room_details['difficulty_rank']),
            "is_culinary": str(room_details['is_culinary']),
            "minimal_people_amount": str(room_details['minimal_people_amount']),
            "maximal_people_amount": str(room_details['maximal_people_amount']) }


def get_time_in_utc():
    time_in_utc_to_return = datetime.now()  # recombee doesnt support our time zone
    print("time is currently:", time_in_utc_to_return)
    return time_in_utc_to_return.timestamp()


# returns a normalized rating with 5 as the nutral
# params:
# user_rating - the rating the user gave a certain room
# return - the rating in a [-1,1] scale
def normalize_user_rating(user_rating):
    final_rating = user_rating - 5
    final_rating = final_rating / 5
    return final_rating


class RecombeeIntegrationClient:
    recombee_client = None

    # initializing a recombee client to send data from
    def __init__(self):
        print("recombee client was initiatlized")
        client = RecombeeClient(DB_NAME, API_KEY)
        self.recombee_client = client

    # sending a user to recombee
    # params:
    # user_id - the id of the new user
    def send_user(self, user_id):
        self.recombee_client.send(AddUser(user_id))

    # sending the user and the viewed room to recombee for assesment
    # params:
    # serialized_room - the room as a serialized JSON
    # user_id - the viewing user's id
    def send_room_viewing(self, room_id, user_id):

        self.recombee_client.send(
            AddDetailView(user_id, room_id, cascade_create=True))
        print("sent viewing of a room", room_id, "  of user ", user_id, " to recombee")

    # sending the user and the finished room to recombee for assesment
    # params:
    # serialized_room - the room as a serialized JSON
    # user_id - the user's id
    # user_rating the room's rating from [0,10], omit empty if not rated
    def send_room_done_by_user(self, room_id, user_id, user_rating=NOT_DONE):

        self.recombee_client.send(AddPurchase(user_id, room_id, cascade_create=True))
        # if he also rated the room - add the ratings
        if user_rating != NOT_DONE:
            self.recombee_client.send(AddRating(user_id, item_id=room_id,
                                                rating=(normalize_user_rating(user_rating)), cascade_create=True))
            print("sent finishing of a room", room_id, "  of user ", user_id, " to recombee")

    # sending the user and the room rating to recombee for assesment
    # params:
    # serialized_room - the room as a serialized JSON
    # user_id - the user's id
    # user_rating the room's rating from [0,10]
    def send_room_rating_by_user(self, room_id, user_id, user_rating):

        self.recombee_client.send(AddRating(user_id, item_id=room_id,
                                            rating=(normalize_user_rating(user_rating)), cascade_create=True))

        print("sent ratings of room:", room_id, "of user:", user_id, "to recombee")

    # cancel room finished by a user
    # params:
    # room_id - the room's id
    # user_id - the user's id
    def cancel_room_done_by_user(self, room_id, user_id):
        self.recombee_client.send(DeletePurchase(user_id, item_id=room_id))
        print("canceled finishing of room:", room_id, "of user:", user_id, "to recombee")

    # updating the user and the room rating to recombee for assesment
    # params:
    # serialized_room - the room as a serialized JSON
    # user_id - the user's id
    # user_rating the room's rating from [0,10]
    def update_room_rating_by_user(self, room_id, user_id, user_rating):
        # TODO maybe batch?
        self.cancel_room_rating_by_user(room_id, user_id)
        self.send_room_rating_by_user(room_id, user_id, user_rating)

        print("updated ratings of room:", room_id, "of user:", user_id, "to recombee")

    # cancel room rating by a user
    # params:
    # room_id - the room's id
    # user_id - the user's id
    def cancel_room_rating_by_user(self, room_id, user_id):
        self.recombee_client.send(DeleteRating(user_id, item_id=room_id))
        print("canceled rating of room:", room_id, "of user:", user_id, "to recombee")

    # initializing a room with the relevant details and sending to recombee
    # params:
    # serialized_room - the room as a serialized JSON
    def init_room_details(self):

        # adding necessary fields to the room
        # self.recombee_client.send((AddItemProperty('id','double')))
        self.recombee_client.send(AddItemProperty('name', 'string'))
        self.recombee_client.send(AddItemProperty('totalRating', 'double'))
        self.recombee_client.send(AddItemProperty('scary_rank', 'double'))
        self.recombee_client.send(AddItemProperty('difficulty_rank', 'double'))
        self.recombee_client.send(AddItemProperty('is_culinary', 'boolean'))
        self.recombee_client.send(AddItemProperty('minimal_people_amount', 'double'))
        self.recombee_client.send(AddItemProperty('maximal_people_amount', 'double'))

    # updating a room with the relevant details and sending to recombee
    # use when updating room ranks or getting new information about it
    # should run at least daily
    # params:
    # serialized_room - the room as a serialized JSON
    def update_room_details(self, serialized_room):
        room_details = serialized_json_to_dict(serialized_room)
        room_json = serialized_room_to_relevant_info_serial(room_details)
        # sending relevant information to recombee
        self.recombee_client.send(SetItemValues(room_details['id'],
                                                room_json,
                                                cascade_create=True
                                                ))

    # updating a room rating after a user rated the room
    # params:
    # serialized_room - the room as a serialized JSON
    def update_room_rating(self, serialized_room):
        self.recombee_client.send(SetItemValues(str(serialized_room.data['id']),
                                                serialized_room_to_relevant_info_serial(serialized_room.data),
                                                cascade_create=True))

    # returning a recommendation of 5 rooms to the user sing recombee's AI
    # params:
    # user-id - the user which requested the recommendation
    # return - the recommendation as a json with room id
    def get_recommendation(self, user_id):
        recommended = self.recombee_client.send(RecommendItemsToUser
                                                (user_id, RECOMMENDATION_SIZE,
                                                 booster=RECOMMENDATION_BOOSTER))
        return recommended['recomms']

    ####### PIPELINE FUNCTIONS #######

    # sends all the rooms from the db to recombee in a batch
    # should run once a day
    def send_rooms_from_db_to_recombee(self):
        rooms_queryset = Room.objects.all()
        requests_to_batch = []
        for room in rooms_queryset:
            room_json = serializers.RoomSerializer(room)
            room_details = serialized_json_to_dict(room_json.data)
            relevant_room_info = serialized_room_to_relevant_info_serial(room_json.data)
            request = SetItemValues(room_details['id'], relevant_room_info, cascade_create=True)
            requests_to_batch.append(request)

        self.recombee_client.send(Batch(requests_to_batch))
        print("finished sending batched rooms to recombee..")

    # sends add the users from the db to recombee in a batch
    # should run when reloading the db into recombee
    def send_users_from_db_to_recombee(self):
        users_queryset = User.objects.all()
        requests_to_batch = []
        for user in users_queryset:
            user_json = serializers.UserSerializer(user)
            user_details = serialized_json_to_dict(user_json.data)
            request = AddUser(user_details['id'])
            requests_to_batch.append(request)

        self.recombee_client.send(Batch(requests_to_batch))
        print("finished sending batched users to recombee..")
