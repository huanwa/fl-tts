from flask import Flask, request, render_template, url_for, jsonify
from tts_voice import tts_order_voice
import edge_tts
import tempfile
import anyio
import os, uuid
import logging

app = Flask(__name__)
#app = Flask(__name__, template_folder='/path/to/your/templates')

language_dict = tts_order_voice

async def text_to_speech_edge(text, language_code):
    try:
        voice = language_dict[language_code]
        communicate = edge_tts.Communicate(text, voice)
        tmp_path = os.path.join(os.path.dirname(__file__), 'static', str(uuid.uuid4()) + ".mp3")

        await communicate.save(tmp_path)

        return "语音合成完成：{}".format(text), tmp_path
    except Exception as e:
        logging.error('Error occurred in text_to_speech_edge: {}'.format(e))
        raise

@app.route('/', methods=['GET', 'POST'])
@app.route('/text_to_speech', methods=['GET', 'POST'])
def text_to_speech():
    if request.method == 'POST':
        data = request.form
        text = data['text']
        language_code = data['language_code']
        try:
            result_text, result_path = anyio.run(text_to_speech_edge, text, language_code)
        except Exception as e:
            logging.error('Error occurred in route text_to_speech: {}'.format(e))
            raise

        # Return as JSON
        return jsonify({
            'result_text': result_text,
            'result_audio_url': url_for('static', filename=os.path.basename(result_path), _external=True)
        })

    else:
        return render_template('text_to_speech.html', languages=language_dict.keys())

if __name__ == "__main__":
    app.run(debug=True)