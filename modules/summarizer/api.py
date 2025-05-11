from flask import Blueprint, request, jsonify
from shared import logger
from modules.auth.decoraters import auth_required
from modules.summarizer.service import SummarizerService

# Create a Flask Blueprint for summarizer endpoints
summarizer_blueprint = Blueprint('summarizer', __name__)
summarizer_service = SummarizerService()

@summarizer_blueprint.route('/status', methods=['GET'])
@auth_required
def get_status():
    """Get the status of the summarizer module"""
    return jsonify({
        "status": "active",
        "module": "summarizer",
        "version": "1.0.0"
    }), 200

@summarizer_blueprint.route('/config', methods=['GET'])
@auth_required
def get_config():
    """Get the current configuration for the summarizer"""
    try:
        config = summarizer_service.get_config()
        return jsonify(config), 200
    except Exception as e:
        logger.error(f"Error getting summarizer config: {e}")
        return jsonify({"error": "Failed to retrieve summarizer configuration"}), 500

@summarizer_blueprint.route('/config', methods=['POST'])
@auth_required
def update_config():
    """Update the configuration for the summarizer"""
    try:
        config_data = request.json
        updated_config = summarizer_service.update_config(config_data)
        return jsonify(updated_config), 200
    except Exception as e:
        logger.error(f"Error updating summarizer config: {e}")
        return jsonify({"error": "Failed to update summarizer configuration"}), 500

@summarizer_blueprint.route('/gemini/test', methods=['POST'])
@auth_required
def test_gemini_connection():
    """Test the connection to the Gemini API"""
    try:
        test_text = request.json.get('text', 'Hello, Gemini!')
        result = summarizer_service.test_gemini_connection(test_text)
        return jsonify({"status": "success", "result": result}), 200
    except Exception as e:
        logger.error(f"Error testing Gemini connection: {e}")
        return jsonify({"status": "error", "message": str(e)}), 500