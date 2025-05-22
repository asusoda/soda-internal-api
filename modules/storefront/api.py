from flask import Blueprint, jsonify

# Flask Blueprint for users
storefront_blueprint = Blueprint("storefront", __name__, template_folder=None, static_folder=None)

@storefront_blueprint.route("/", methods=["GET"])
def storefront_index():
    return jsonify({"message": "storefront api"}), 200

