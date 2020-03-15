from core.models import Review, Game, Room
from django.contrib.auth import get_user_model, authenticate
from rest_framework import serializers


class UserNameSerializer(serializers.ModelSerializer):
    class Meta:
        model = get_user_model()
        fields = ('first_name', 'last_name', 'id')


class RoomNameSerializer(serializers.ModelSerializer):
    class Meta:
        model = Room
        fields = ('id', 'name', 'owner')
        read_only_fields = ('id',)


class ReviewSerializer(serializers.ModelSerializer):
    class Meta:
        model = Review
        fields = (
            'id', 'game', 'commentDate', 'title', 'text', 'scary', 'difficulty', 'scenery', 'totalRating')
        read_only_fields = ('id', 'commentDate')
        extra_kwargs = {'totalRating': {'required': True, 'error_messages': {'required': 'חובה לדרג את החדר'}}}

    def validate_totalRating(self, value):
        if value > 10 or value < 1:
            raise serializers.ValidationError('הדירוג צריך להיות בין 1 ל-10')
        return value

    def validate_scary(self, value):
        if value > 10 or value < 0:
            raise serializers.ValidationError('דירוג הפחד צריך להיות בין 0 ל-10')
        return value

    def validate_difficulty(self, value):
        if value > 3 or value < 0:
            raise serializers.ValidationError('דירוג הקושי צריך להיות בין 0 ל-3')
        return value

    def to_representation(self, instance):
        represent = super(ReviewSerializer, self).to_representation(instance)
        game = Game.objects.get(pk=represent['game'])
        represent['user'] = {'first_name': game.user.first_name,
                             'last_name': game.user.last_name, 'id': game.user.id}
        return represent

    def update(self, instance, validated_data):
        validated_data.pop('game', None)
        return super().update(instance, validated_data)


class RoomSerializer(serializers.ModelSerializer):
    class Meta:
        model = Room
        fields = (
            'id', 'name', 'description', 'address', 'website', 'duration', 'telephone_num',
            'difficulty_rank_count', 'owner', 'is_culinary', 'is_kids',
            'scary_rank_count', 'minimal_people_amount', 'large_image', 'room_tile_image',
            'totalRating_count', 'maximal_people_amount', 'pub_date', 'city', 'latitude', 'longitude')
        read_only_fields = ('id',)

    def to_representation(self, instance):
        represent = super(RoomSerializer, self).to_representation(instance)
        if instance.totalRating_count > 0:
            represent['totalRating'] = round(instance.totalRating / instance.totalRating_count, 1)
        else:
            represent['totalRating'] = 0
        if instance.scary_rank_count > 0:
            represent['scary_rank'] = round(instance.scary_rank / instance.scary_rank_count, 1)
        else:
            represent['scary_rank'] = 0
        if instance.difficulty_rank_count > 0:
            represent['difficulty_rank'] = round(instance.difficulty_rank / instance.difficulty_rank_count, 1)
        else:
            represent['difficulty_rank'] = 0

        request = self.context.get('request')
        if (request is None) or (not (hasattr(request, "user"))) or (not request.user.is_authenticated):
            represent['already_rated'] = False
        else:
            represent['already_rated'] = len(
                Review.objects.filter(game__user=request.user, game__room__id=instance.id)) > 0
        return represent


class GameSerializer(serializers.ModelSerializer):
    room = RoomNameSerializer(many=False, read_only=True)

    class Meta:
        model = Game
        fields = ('id', 'user', 'room', 'date', 'time', 'otherPlayers')
        read_only_fields = ('id', 'user')
        extra_kwargs = {'date': {'format': "%Y-%m-%dT%H:%M:%S.%f%z"}}

    def validate_time(self, value):
        if not 0 <= value <= 240:
            raise serializers.ValidationError('הזמן צריך להיות בין 0 ל-240')
        return value

    # def validate_room(self, value):
    #     try:
    #         Room.objects.get(id=value)
    #     except Room.DoesNotExist:
    #         raise serializers.ValidationError('לא נמצא חדר')
    #     return value

    def to_representation(self, instance):
        representation = super(GameSerializer, self).to_representation(instance)
        representation.pop('user', None)
        try:
            review = Review.objects.get(game=instance)
            representation['review'] = ReviewSerializer(review).data
        finally:
            return representation

    def update(self, instance, validated_data):
        validated_data.pop('room', None)
        return super().update(instance, validated_data)


class UserSerializer(serializers.ModelSerializer):
    game = GameSerializer(read_only=True, many=True)

    class Meta:
        model = get_user_model()
        fields = (
            'id', 'email', 'password', 'first_name', 'last_name', 'rooms_count', 'reviews_count',
            'average_time', 'room_time_count', 'searchable', 'game')
        extra_kwargs = {'password': {'write_only': True, 'min_length': 5}}

    def create(self, validated_data):
        validated_data.pop('room_time_count', None)
        validated_data.pop('rooms_count', None)
        validated_data.pop('reviews_count', None)
        validated_data.pop('average_time', None)
        return get_user_model().objects.create_user(**validated_data)

    def update(self, instance, validated_data):
        validated_data.pop('room_time_count', None)
        validated_data.pop('rooms_count', None)
        validated_data.pop('reviews_count', None)
        validated_data.pop('average_time', None)
        password = validated_data.pop('password', None)
        user = super().update(instance, validated_data)

        if password:
            user.set_password(password)
            user.save()

        return user

    def to_representation(self, instance):
        represent = super(UserSerializer, self).to_representation(instance)
        if instance.room_time_count > 0:
            represent['average_time'] = round(instance.average_time / instance.room_time_count, 1)
        return represent


class AuthTokenSerializer(serializers.Serializer):
    email = serializers.CharField()
    password = serializers.CharField(
        style={'input_type': 'password'},
        trim_whitespace=False
    )

    def validate(self, attrs):
        email = attrs.get('email')
        password = attrs.get('password')

        user = authenticate(request=self.context.get('request'),
                            username=email,
                            password=password)
        if not user:
            msg = 'Unable to authenticate with provided credentials'
            raise serializers.ValidationError(msg, code='authentication')

        attrs['user'] = user
        return attrs


class SocialSerializer(serializers.Serializer):
    """
    Serializer which accepts an OAuth2 access token and provider.
    """
    provider = serializers.CharField(max_length=255, required=True)
    access_token = serializers.CharField(max_length=4096, required=True, trim_whitespace=True)
