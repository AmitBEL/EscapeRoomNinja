from django.db.models import Avg
from rest_framework import status
from rest_framework.test import APITestCase

from .models import Room, Review, User, Game
from .serializers import RoomSerializer, UserSerializer, GameSerializer, ReviewSerializer


class SystemTest(APITestCase):
    fixtures = ['roomTestData.json', ]
    token = None

    def setUp(self):
        data = {'email': 'test@gmail.com', 'password': 'test1234',
                'last_name': 'test last name', 'first_name': 'test first name'}
        User.objects.create_user(**data)

    def test_get_rooms(self):
        """
        Ensure we get the correct number of rooms.
        """
        url = '/api/room/'
        response = self.client.get(url, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(Room.objects.count(), response.data['count'])

    def test_room_rating(self):
        """
        Ensure the rooms rating is correct.
        """
        url_prefix = '/api/room/'
        url_suffix = '/review/'
        rooms = RoomSerializer(Room.objects.all(), many=True)
        for room in rooms.data:
            url = url_prefix + str(room['id']) + url_suffix
            response = self.client.get(url, format='json')
            self.assertEqual(response.status_code, status.HTTP_200_OK)
            roomReview = Review.objects.filter(game__room__pk=room['id'])
            self.assertEqual(roomReview.count(), len(response.data['results']))
            self.assertEqual(room['totalRating_count'], len(response.data['results']))
            roomAverage = roomReview.aggregate(Avg('totalRating'))['totalRating__avg'] or 0
            self.assertEqual(roomAverage, float(room['totalRating']))

    def test_create_user_success(self):
        url = '/api/user/create/'
        data = {'email': 'yotam@gmail.com', 'password': '123456',
                'first_name': 'yotam', 'last_name': 'hadas'}
        response = self.client.post(url, data=data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('token', response.data)

    def test_create_user_failure_email(self):
        url = '/api/user/create/'
        data = {'email': 'yotamgmail.com', 'password': '123456',
                'first_name': 'yotam', 'last_name': 'hadas'}
        response = self.client.post(url, data=data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_user_failure_password(self):
        url = '/api/user/create/'
        data = {'email': 'yotam@gmail.com', 'password': '',
                'first_name': 'yotam', 'last_name': 'hadas'}
        response = self.client.post(url, data=data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_create_user_failure_name(self):
        url = '/api/user/create/'
        data = {'email': 'yotam@gmail.com', 'password': '123456', 'last_name': 'hadas'}
        response = self.client.post(url, data=data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_user_success(self):
        url = '/api/user/token/'
        data = {'email': 'test@gmail.com', 'password': 'test1234'}
        response = self.client.post(url, data=data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('token', response.data)
        self.token = response.data['token']

    def test_user_profile_no_auth(self):
        url = '/api/user/profile/'
        response = self.client.post(url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

        response = self.client.get(url, HTTP_AUTHORIZATION='Token ')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_user_profile_with_auth(self):
        url = '/api/user/profile/'
        self.test_login_user_success()
        data = {'token': 'Token ' + self.token}

        response = self.client.get(url, HTTP_AUTHORIZATION=data['token'])
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_user_flow_games(self):
        number_of_rooms = 5
        create_user_url = '/api/user/create/'
        data = {'email': 'yotam@gmail.com', 'password': '123456',
                'first_name': 'yotam', 'last_name': 'hadas'}
        user_response = self.client.post(create_user_url, data=data)
        token = 'Token ' + user_response.data['token']
        game_url = '/api/user/game/'
        self.client.credentials(HTTP_AUTHORIZATION=token)
        for i in range(1, number_of_rooms + 1):
            game_response = self.client.post(game_url, data={'room': i, 'time': 0})
            self.assertEqual(game_response.status_code, status.HTTP_201_CREATED)

        user = UserSerializer(User.objects.get(email=data['email']))
        user = user.data
        game_response = self.client.get(game_url)
        self.assertEqual(game_response.status_code, status.HTTP_200_OK)
        games = GameSerializer(Game.objects.filter(user=user_response.data['user']['id']), many=True)
        self.assertEqual(number_of_rooms, len(game_response.data))
        self.assertEqual(len(games.data), number_of_rooms)
        self.assertEqual(user['rooms_count'], number_of_rooms)

        for i in range(1, number_of_rooms + 1):
            game_response = self.client.delete(game_url + str(i) + '/')
            self.assertEqual(game_response.status_code, status.HTTP_204_NO_CONTENT)

        user = UserSerializer(User.objects.get(email=data['email']))
        user = user.data
        game_response = self.client.get(game_url)
        self.assertEqual(game_response.status_code, status.HTTP_200_OK)
        games = GameSerializer(Game.objects.filter(user=user_response.data['user']['id']), many=True)
        self.assertEqual(0, len(game_response.data))
        self.assertEqual(len(games.data), 0)
        self.assertEqual(user['rooms_count'], 0)
        self.assertEqual(user['room_time_count'], 0)

    def test_post_review_delete_review_only_total(self):
        room_id = 1
        create_user_url = '/api/user/create/'
        data = {'email': 'yotam@gmail.com', 'password': '123456',
                'first_name': 'yotam', 'last_name': 'hadas'}
        user_response = self.client.post(create_user_url, data=data)
        create_review_url = '/api/room/' + str(room_id) + '/review/'
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + user_response.data['token'])
        create_review_response = self.client.post(create_review_url,
                                                  data={'totalRating': 9, 'text': 'This is a test review'})
        self.assertEqual(create_review_response.status_code, status.HTTP_201_CREATED)
        created_review = ReviewSerializer(Review.objects.get(id=create_review_response.data['id']))
        self.assertEqual(create_review_response.data['text'], created_review.data['text'])
        user = UserSerializer(User.objects.get(email=data['email']))
        room = RoomSerializer(Room.objects.get(id=room_id))
        game = GameSerializer(Game.objects.get(id=room_id, user=user.data['id']))

        self.assertEqual(user.data['room_time_count'], 0)
        self.assertEqual(user.data['average_time'], 0)
        self.assertEqual(user.data['rooms_count'], 1)
        self.assertEqual(user.data['reviews_count'], 1)

        self.assertEqual(room.data['totalRating'], 9)
        self.assertEqual(room.data['totalRating_count'], 1)
        self.assertEqual(float(room.data['scary_rank']), 0)
        self.assertEqual(float(room.data['difficulty_rank']), 0)
        self.assertEqual(float(room.data['difficulty_rank_count']), 0)
        self.assertEqual(float(room.data['scary_rank_count']), 0)

        self.assertEqual(game.data['room']['id'], room_id)

        ### DELETE THE REVIEW ###

        delete_review_response = self.client.delete(create_review_url + str(created_review.data['id']) + '/')

        self.assertEqual(delete_review_response.status_code, status.HTTP_204_NO_CONTENT)

        user = UserSerializer(User.objects.get(email=data['email']))
        room = RoomSerializer(Room.objects.get(id=room_id))
        game = GameSerializer(Game.objects.get(id=room_id, user=user.data['id']))

        self.assertEqual(user.data['room_time_count'], 0)
        self.assertEqual(user.data['average_time'], 0)
        self.assertEqual(user.data['rooms_count'], 1)
        self.assertEqual(user.data['reviews_count'], 0)

        self.assertEqual(float(room.data['totalRating']), 0)
        self.assertEqual(float(room.data['totalRating_count']), 0)
        self.assertEqual(float(room.data['scary_rank']), 0)
        self.assertEqual(float(room.data['difficulty_rank']), 0)
        self.assertEqual(float(room.data['difficulty_rank_count']), 0)
        self.assertEqual(float(room.data['scary_rank_count']), 0)

        self.assertEqual(game.data['room']['id'], room_id)

    def test_post_review_delete_review_all(self):
        room_id = 1
        create_user_url = '/api/user/create/'
        data = {'email': 'yotam@gmail.com', 'password': '123456',
                'first_name': 'yotam', 'last_name': 'hadas'}
        user_response = self.client.post(create_user_url, data=data)
        create_review_url = '/api/room/' + str(room_id) + '/review/'
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + user_response.data['token'])
        create_review_response = self.client.post(create_review_url,
                                                  data={'totalRating': 9, 'text': 'This is a test review',
                                                        'difficulty': 2, 'scary': 7})
        self.assertEqual(create_review_response.status_code, status.HTTP_201_CREATED)
        created_review = ReviewSerializer(Review.objects.get(id=create_review_response.data['id']))
        self.assertEqual(create_review_response.data['text'], created_review.data['text'])
        user = UserSerializer(User.objects.get(email=data['email']))
        room = RoomSerializer(Room.objects.get(id=room_id))
        game = GameSerializer(Game.objects.get(id=room_id, user=user.data['id']))

        self.assertEqual(user.data['room_time_count'], 0)
        self.assertEqual(user.data['average_time'], 0)
        self.assertEqual(user.data['rooms_count'], 1)
        self.assertEqual(user.data['reviews_count'], 1)

        self.assertEqual(room.data['totalRating'], 9)
        self.assertEqual(room.data['totalRating_count'], 1)
        self.assertEqual(float(room.data['scary_rank']), 7)
        self.assertEqual(float(room.data['difficulty_rank']), 2)
        self.assertEqual(float(room.data['difficulty_rank_count']), 1)
        self.assertEqual(float(room.data['scary_rank_count']), 1)

        self.assertEqual(game.data['room']['id'], room_id)

        ### DELETE THE REVIEW ###

        delete_review_response = self.client.delete(create_review_url + str(created_review.data['id']) + '/')

        self.assertEqual(delete_review_response.status_code, status.HTTP_204_NO_CONTENT)

        user = UserSerializer(User.objects.get(email=data['email']))
        room = RoomSerializer(Room.objects.get(id=room_id))
        game = GameSerializer(Game.objects.get(id=room_id, user=user.data['id']))

        self.assertEqual(user.data['room_time_count'], 0)
        self.assertEqual(user.data['average_time'], 0)
        self.assertEqual(user.data['rooms_count'], 1)
        self.assertEqual(user.data['reviews_count'], 0)

        self.assertEqual(float(room.data['totalRating']), 0)
        self.assertEqual(float(room.data['totalRating_count']), 0)
        self.assertEqual(float(room.data['scary_rank']), 0)
        self.assertEqual(float(room.data['difficulty_rank']), 0)
        self.assertEqual(float(room.data['difficulty_rank_count']), 0)
        self.assertEqual(float(room.data['scary_rank_count']), 0)

        self.assertEqual(game.data['room']['id'], room_id)

    def test_post_2_reviews_to_same_room_failure(self):
        room_id = 1
        create_user_url = '/api/user/create/'
        data = {'email': 'yotam@gmail.com', 'password': '123456',
                'first_name': 'yotam', 'last_name': 'hadas'}
        user_response = self.client.post(create_user_url, data=data)
        create_review_url = '/api/room/' + str(room_id) + '/review/'
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + user_response.data['token'])
        create_review_response = self.client.post(create_review_url,
                                                  data={'totalRating': 9, 'text': 'This is a test review',
                                                        'difficulty': 2, 'scary': 7})
        self.assertEqual(create_review_response.status_code, status.HTTP_201_CREATED)
        create_review_response = self.client.post(create_review_url,
                                                  data={'totalRating': 9, 'text': 'This is a test review',
                                                        'difficulty': 2, 'scary': 7})
        self.assertEqual(create_review_response.status_code, status.HTTP_403_FORBIDDEN)

    def test_multiple_reviews(self):
        create_user_url = '/api/user/create/'
        data1 = {'email': 'yotam@gmail.com', 'password': '123456',
                 'first_name': 'yotam', 'last_name': 'hadas'}
        user_response = self.client.post(create_user_url, data=data1)

        data2 = {'email': 'yotam2@gmail.com', 'password': '123456',
                 'first_name': 'yotam', 'last_name': 'hadas'}
        user_response2 = self.client.post(create_user_url, data=data2)

        data3 = {'email': 'yotam3@gmail.com', 'password': '123456',
                 'first_name': 'yotam', 'last_name': 'hadas'}
        user_response3 = self.client.post(create_user_url, data=data3)

        create_review_url = '/api/room/' + str(1) + '/review/'
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + user_response.data['token'])
        create_review_response1 = self.client.post(create_review_url,
                                                   data={'totalRating': 9, 'text': 'This is a test review',
                                                         'difficulty': 2, 'scary': 7})
        self.assertEqual(create_review_response1.status_code, status.HTTP_201_CREATED)

        self.client.credentials(HTTP_AUTHORIZATION='Token ' + user_response2.data['token'])
        create_review_response2 = self.client.post(create_review_url,
                                                   data={'totalRating': 5, 'text': 'This is a test review',
                                                         'scary': 7})
        self.assertEqual(create_review_response2.status_code, status.HTTP_201_CREATED)

        self.client.credentials(HTTP_AUTHORIZATION='Token ' + user_response3.data['token'])
        create_review_response3 = self.client.post(create_review_url,
                                                   data={'totalRating': 8, 'text': 'This is a test review',
                                                         'difficulty': 2, 'scary': 3})
        self.assertEqual(create_review_response3.status_code, status.HTTP_201_CREATED)

        room = RoomSerializer(Room.objects.get(id=1))

        self.assertEqual(float(room.data['totalRating']), round((9 + 5 + 8) / 3,1))
        self.assertEqual(float(room.data['totalRating_count']), 3)
        self.assertEqual(float(room.data['scary_rank']), round((7 + 7 + 3) / 3,1))
        self.assertEqual(float(room.data['difficulty_rank']), (2 + 2) / 2)
        self.assertEqual(float(room.data['difficulty_rank_count']), 2)
        self.assertEqual(float(room.data['scary_rank_count']), 3)

        ### DELETE REVIEWS

        self.client.credentials(HTTP_AUTHORIZATION='Token ' + user_response3.data['token'])
        delete_review_response = self.client.delete(create_review_url + '3/')
        self.assertEqual(delete_review_response.status_code, status.HTTP_204_NO_CONTENT)

        room = RoomSerializer(Room.objects.get(id=1))

        self.assertEqual(float(room.data['totalRating']), (9 + 5) / 2)
        self.assertEqual(float(room.data['totalRating_count']), 2)
        self.assertEqual(float(room.data['scary_rank']), (7 + 7) / 2)
        self.assertEqual(float(room.data['difficulty_rank']), (2) / 1)
        self.assertEqual(float(room.data['difficulty_rank_count']), 1)
        self.assertEqual(float(room.data['scary_rank_count']), 2)

        self.client.credentials(HTTP_AUTHORIZATION='Token ' + user_response2.data['token'])
        delete_review_response = self.client.delete(create_review_url + '2/')
        self.assertEqual(delete_review_response.status_code, status.HTTP_204_NO_CONTENT)

        room = RoomSerializer(Room.objects.get(id=1))

        self.assertEqual(float(room.data['totalRating']), (9) / 1)
        self.assertEqual(float(room.data['totalRating_count']), 1)
        self.assertEqual(float(room.data['scary_rank']), (7) / 1)
        self.assertEqual(float(room.data['difficulty_rank']), (2) / 1)
        self.assertEqual(float(room.data['difficulty_rank_count']), 1)
        self.assertEqual(float(room.data['scary_rank_count']), 1)

        self.client.credentials(HTTP_AUTHORIZATION='Token ' + user_response.data['token'])
        delete_review_response = self.client.delete(create_review_url + '1/')
        self.assertEqual(delete_review_response.status_code, status.HTTP_204_NO_CONTENT)

        room = RoomSerializer(Room.objects.get(id=1))

        self.assertEqual(float(room.data['totalRating']), 0)
        self.assertEqual(float(room.data['totalRating_count']), 0)
        self.assertEqual(float(room.data['scary_rank']), 0)
        self.assertEqual(float(room.data['difficulty_rank']), 0)
        self.assertEqual(float(room.data['difficulty_rank_count']), 0)
        self.assertEqual(float(room.data['scary_rank_count']), 0)

        create_review_response = self.client.post(create_review_url,
                                                  data={'totalRating': 9, 'text': 'This is a test review',
                                                        'difficulty': 2, 'scary': 7})

        self.assertEqual(create_review_response.status_code, status.HTTP_201_CREATED)

        room = RoomSerializer(Room.objects.get(id=1))

        self.assertEqual(float(room.data['totalRating']), 9)
        self.assertEqual(float(room.data['totalRating_count']), 1)
        self.assertEqual(float(room.data['scary_rank']), 7)
        self.assertEqual(float(room.data['difficulty_rank']), 2)
        self.assertEqual(float(room.data['difficulty_rank_count']), 1)
        self.assertEqual(float(room.data['scary_rank_count']), 1)

    def test_delete_other_user_review(self):
        create_user_url = '/api/user/create/'
        data1 = {'email': 'yotam@gmail.com', 'password': '123456',
                 'first_name': 'yotam', 'last_name': 'hadas'}
        user_response = self.client.post(create_user_url, data=data1)

        data2 = {'email': 'yotam2@gmail.com', 'password': '123456',
                 'first_name': 'yotam', 'last_name': 'hadas'}
        user_response2 = self.client.post(create_user_url, data=data2)

        create_review_url = '/api/room/' + str(1) + '/review/'
        self.client.credentials(HTTP_AUTHORIZATION='Token ' + user_response.data['token'])
        create_review_response1 = self.client.post(create_review_url,
                                                   data={'totalRating': 9, 'text': 'This is a test review',
                                                         'difficulty': 2, 'scary': 7})
        self.assertEqual(create_review_response1.status_code, status.HTTP_201_CREATED)

        self.client.credentials(HTTP_AUTHORIZATION='Token ' + user_response2.data['token'])
        create_review_response2 = self.client.post(create_review_url,
                                                   data={'totalRating': 5, 'text': 'This is a test review',
                                                         'scary': 7})
        self.assertEqual(create_review_response2.status_code, status.HTTP_201_CREATED)

        self.client.credentials()
        delete_review_response = self.client.delete(create_review_url + '1/')

        self.assertEqual(delete_review_response.status_code, status.HTTP_401_UNAUTHORIZED)

        self.client.credentials(HTTP_AUTHORIZATION='Token ' + user_response2.data['token'])
        delete_review_response = self.client.delete(create_review_url + '1/')

        self.assertEqual(delete_review_response.status_code, status.HTTP_403_FORBIDDEN)

        delete_review_response = self.client.delete(create_review_url + '2/')

        self.assertEqual(delete_review_response.status_code, status.HTTP_204_NO_CONTENT)

    def test_add_review_to_exiting_user_game(self):
        create_user_url = '/api/user/create/'
        create_review_url = '/api/room/' + str(1) + '/review/'
        data = {'email': 'yotam@gmail.com', 'password': '123456',
                'first_name': 'yotam', 'last_name': 'hadas'}
        user_response = self.client.post(create_user_url, data=data)
        token = 'Token ' + user_response.data['token']
        game_url = '/api/user/game/'
        self.client.credentials(HTTP_AUTHORIZATION=token)
        game_response = self.client.post(game_url, data={'room': 1, 'time': 30})
        self.assertEqual(game_response.status_code, status.HTTP_201_CREATED)
        create_review_response = self.client.post(create_review_url,
                                                  data={'totalRating': 9, 'text': 'This is a test review',
                                                        'difficulty': 2, 'scary': 7})

        user = UserSerializer(User.objects.get(email=data['email']))
        room = RoomSerializer(Room.objects.get(id=1))
        game = GameSerializer(Game.objects.get(id=1, user=user.data['id']))

        self.assertEqual(user.data['room_time_count'], 1)
        self.assertEqual(user.data['average_time'], 30)
        self.assertEqual(user.data['rooms_count'], 1)
        self.assertEqual(user.data['reviews_count'], 1)

        self.assertEqual(room.data['totalRating'], 9)
        self.assertEqual(room.data['totalRating_count'], 1)
        self.assertEqual(float(room.data['scary_rank']), 7)
        self.assertEqual(float(room.data['difficulty_rank']), 2)
        self.assertEqual(float(room.data['difficulty_rank_count']), 1)
        self.assertEqual(float(room.data['scary_rank_count']), 1)

        self.assertEqual(game.data['room']['id'], 1)
