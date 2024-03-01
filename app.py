from flask import Flask, request, render_template, jsonify, url_for
from tts_voice import tts_order_voice
import edge_tts
import anyio
import os, uuid
from collections import defaultdict
import datetime
import random
import string
from flask_cors import CORS
from werkzeug.middleware.proxy_fix import ProxyFix
from flask import send_file
from flask import send_from_directory

languages = defaultdict(list)
for description, code in tts_order_voice.items():
    language_description = description.split('(')[0]  # 提取语言描述，例如 "English (United States)"
    languages[language_description].append((description, code))  # 添加对应的完整描述和代码


languages = dict(languages)


app = Flask(__name__)
language_dict = tts_order_voice
CORS(app, origins="https://luvvoice.com")
app.config['PREFERRED_URL_SCHEME'] = 'https'
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)
app.config['UPLOAD_FOLDER'] = '/var/www/fl-tts/static'

async def text_to_speech_edge(text, language_code):
    voice = language_code
    communicate = edge_tts.Communicate(text, voice)
    date_str = datetime.datetime.now().strftime("%Y%m%d")
    random_str = ''.join(random.choices(string.ascii_letters + string.digits, k=4))
    domain_name = 'luvvoice.com'
    filename = f"{domain_name}-{date_str}-{random_str}.mp3"
    static_dir=os.path.join('/var/www/fl-tts/static')
    tmp_path = os.path.join(static_dir,filename)

    await communicate.save(tmp_path)

    return "语音合成完成：{}".format(text), filename 
# 注意我返回的是文件名而不是完整路径，以便于下面生成URL


@app.route('/', methods=['GET'])
def index():
    # 只需负责呈现主页面
    return render_template('index.html', languages=languages)


@app.route('/text_to_speech', methods=['POST'])
def handle_text_to_speech():
    data = request.form
    text = data['text']
    language_code = data['language_code']
    result_text, result_filename = anyio.run(text_to_speech_edge, text, language_code)
    
    # 生成音频文件的路径
    result_audio_path = generate_audio_file(result_filename)
    
    # 直接返回音频文件
    return send_from_directory(app.config['UPLOAD_FOLDER'], result_filename, as_attachment=True, download_name='audio.mp3')

def generate_audio_file(filename):
    # 生成音频文件的路径
    static_dir = os.path.join(app.root_path, 'static')
    result_audio_path = os.path.join(static_dir, filename)
    return result_audio_path
    

@app.route('/tos', methods=['GET']) 
def tos():
    return render_template('terms_of_service.html')



@app.route('/language/<language>')
def language_route(language):
    # 根据选择的语言显示对应的声音
    voices = languages.get(language)
    if voices:
        return render_template('language.html', selected_language=language, languages=languages, voices=voices)
    else:
        return 'Language not supported', 404


@app.route('/voice/<voice_code>')
def voice_route(voice_code):
    # 根据选择的声音代码找到对应的语言和描述
    for language, voices in languages.items():
        for desc, code in voices:
            if code == voice_code:
                # 渲染和特定语言相关的声音列表
                return render_template('language.html', selected_language=language, languages=languages, voices=languages[language], selected_voice=voice_code)
    return 'Voice code not supported', 404


@app.route('/ads.txt')
def ads_txt():
    return app.send_static_file('ads.txt')


@app.route('/privacy-policy', methods=['GET'])
def privacy_policy():
    return render_template('privacy-policy.html')


if __name__ == "__main__":
    app.run()
