from flask import Flask, jsonify, request
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from math import radians, sin, cos, sqrt, atan2

app = Flask(__name__)
CORS(app)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///TCM.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
migrate = Migrate(app, db)

class Utility:
    @staticmethod
    def are_coordinates_close(lat1, lon1, lat2, lon2, radius=6371.0, proximity_threshold=0.1):
        lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])

        dlat = lat2 - lat1
        dlon = lon2 - lon1

        a = sin(dlat / 2)**2 + cos(lat1) * cos(lat2) * sin(dlon / 2)**2
        c = 2 * atan2(sqrt(a), sqrt(1 - a))

        distance = radius * c

        return distance <= proximity_threshold

class Category(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)

class Places(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    category_id = db.Column(db.Integer, nullable=False)
    name = db.Column(db.String(255), nullable=False)
    latitude = db.Column(db.Float(255), nullable=False)
    longitude = db.Column(db.Float(255), nullable=False)

class Route(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)

class RoutePoint(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    route_id = db.Column(db.Integer, db.ForeignKey('route.id'), nullable=False)
    place_id = db.Column(db.Integer, db.ForeignKey('places.id'), nullable=False)
    order = db.Column(db.Integer, nullable=False)
    place = db.relationship('Places', backref='route_points')

class RouteReview(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    route_id = db.Column(db.Integer, db.ForeignKey('route.id'), nullable=False)
    user_id = db.Column(db.Integer, nullable=False)
    review_text = db.Column(db.Text, nullable=False)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    coins = db.Column(db.Integer, default=0)
    visitedRoute = db.Column(db.Boolean, default=False)
    visitedPlaces = db.relationship('Places', secondary='user_visited_places')

class UserVisitedPlaces(db.Model):
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), primary_key=True)
    route_id = db.Column(db.Integer, db.ForeignKey('route.id'))
    place_id = db.Column(db.Integer, db.ForeignKey('places.id'), primary_key=True)

class RoutesAPI:
    @staticmethod
    @app.route('/categories', methods=['GET'])
    def get_categories():
        categories = Category.query.all()
        categories_data = [{"id": category.id, "name": category.name} for category in categories]
        return jsonify(categories_data)

    @staticmethod
    @app.route('/categories/<int:category_id>', methods=['GET'])
    def get_category(category_id):
        category = Category.query.get(category_id)
        if category is not None:
            return jsonify({"id": category.id, "name": category.name})
        else:
            return jsonify({"error": "Категория не найдена"}), 404

    @staticmethod
    @app.route('/places/search', methods=['POST'])
    def search_places():
        try:
            data = request.get_json()
            categories_ids = data.get('categories', [])

            if not isinstance(categories_ids, list) or not categories_ids:
                return jsonify({"error": "Некорректные данные для поиска"}), 400

            places = Places.query.filter(Places.category_id.in_(categories_ids)).all()

            places_data = [
                {"id": place.id, "category_id": place.category_id, "name": place.name,
                 "latitude": place.latitude, "longitude": place.longitude}
                for place in places
            ]

            return jsonify(places_data)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @staticmethod
    @app.route('/routes', methods=['GET'])
    def get_routes():
        routes = Route.query.all()
        routes_data = []
        for route in routes:
            places = RoutePoint.query.filter_by(route_id=route.id).order_by(RoutePoint.order).all()
            places_data = [{'id': place.id, 'name': place.place.name} for place in places]
            routes_data.append({'id': route.id, 'name': route.name, 'places': places_data})
        return jsonify(routes_data)

    @staticmethod
    @app.route('/routes/<int:route_id>', methods=['GET'])
    def get_route(route_id):
        route = Route.query.get(route_id)
        if route is not None:
            places = RoutePoint.query.filter_by(route_id=route.id).order_by(RoutePoint.order).all()
            places_data = [{'id': place.id, 'name': place.place.name, 'latitude': place.place.latitude,
                            'longitude': place.place.longitude} for place in places]
            return jsonify({'id': route.id, 'name': route.name, 'places': places_data})
        else:
            return jsonify({"error": "Маршрут не найден"}), 404

    @staticmethod
    @app.route('/routes/<int:route_id>/reviews', methods=['GET'])
    def get_route_reviews(route_id):
        reviews = RouteReview.query.filter_by(route_id=route_id).all()
        reviews_data = [{"id": review.id, "review_text": review.review_text, "user_id": review.user_id} for review in
                        reviews]
        return jsonify(reviews_data)

    @staticmethod
    @app.route('/routes/<int:route_id>/reviews', methods=['POST'])
    def add_route_review(route_id):
        try:
            data = request.get_json()
            review_text = data.get('review_text', '')
            user_id = data.get('user_id', '')

            if not review_text or not user_id:
                return jsonify({"error": "Отзыв или айди пользователя не могут быть пустыми"}), 400

            review = RouteReview(route_id=route_id, user_id=user_id, review_text=review_text)
            db.session.add(review)
            db.session.commit()

            return jsonify({"success": "Отзыв успешно добавлен"})
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @staticmethod
    @app.route('/routes/<int:route_id>/<int:order_id>/check-in', methods=['POST'])
    def check_in_place(route_id, order_id):
        try:
            data = request.get_json()
            user_id = data.get('userId')
            user_latitude = data.get('latitude')
            user_longitude = data.get('longitude')

            route_point = RoutePoint.query.filter_by(route_id=route_id, order=order_id).first()
            if not route_point:
                return jsonify({"error": "Invalid route_id or order_id"}), 404

            place_id = route_point.place_id

            place = Places.query.get(place_id)
            if not place:
                return jsonify({"error": "Place not found"}), 404

            if Utility.are_coordinates_close(place.latitude, place.longitude, user_latitude, user_longitude):
                user = User.query.get(user_id)

                if not user:
                    user = User(id=user_id, coins=0, visitedRoute=False)
                    db.session.add(user)
                    db.session.commit()

                visited_place = UserVisitedPlaces.query.filter_by(user_id=user_id, place_id=place_id,
                                                                   route_id=route_id).first()
                if visited_place:
                    return jsonify({"error": "Place in the current route has already been visited"}), 451
                else:
                    visited_place = UserVisitedPlaces(user_id=user_id, place_id=place_id, route_id=route_id)
                    db.session.add(visited_place)

                    user.coins += 10
                    db.session.commit()

                    if route_id:
                        route_points = RoutePoint.query.filter_by(route_id=route_id).all()
                        visited_places = UserVisitedPlaces.query.filter_by(user_id=user_id, route_id=route_id).all()

                        if set(route_points) <= set(visited_places):
                            user.visitedRoute = True
                            user.coins += 100
                            db.session.commit()

                    return jsonify({"success": "Place successfully visited!"})
            else:
                return jsonify({"error": "You are outside the proximity of the place or do not belong to the route"}), 452
        except Exception as e:
            return jsonify({"error": str(e)}), 500

class UsersAPI:
    @staticmethod
    @app.route('/users/<int:user_id>/coins', methods=['GET'])
    def get_coins(user_id):
        try:
            user = User.query.get(user_id)
            if user is not None:
                coins = user.coins
                return jsonify({"user_id": user_id, "coins": coins})
            else:
                return jsonify({"user_id": 404, "coins": 0}), 404
        except Exception as e:
            return jsonify({"error": str(e)}), 500

    @staticmethod
    @app.route('/users/<int:user_id>/visited-places/<int:route_id>', methods=['GET'])
    def get_user_visited_places(user_id, route_id):
        try:
            visited_places = UserVisitedPlaces.query.filter_by(user_id=user_id, route_id=route_id).all()
            visited_places_data = [{"place_id": place.place_id} for place in visited_places]
            return jsonify(visited_places_data)
        except Exception as e:
            return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(host='0.0.0.0', port=5000)
