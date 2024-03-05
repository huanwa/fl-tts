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
from flask import send_from_directory
from botocore.client import Config
import mimetypes
import boto3

languages = defaultdict(list)
for description, code in tts_order_voice.items():
    language_description = description.split('(')[0]  # 提取语言描述，例如 "English (United States)"
    languages[language_description].append((description, code))  # 添加对应的完整描述和代码


languages = dict(languages)
CLOUDFLARE_R2_BUCKET_URL = 'https://pub-8a6c901f26754c4bbd4f79e70e61d104.r2.dev'

app = Flask(__name__)
language_dict = tts_order_voice
CORS(app)
app.config['PREFERRED_URL_SCHEME'] = 'https'
app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)


async def text_to_speech_edge(text, language_code):
    voice = language_code
    communicate = edge_tts.Communicate(text, voice)
    date_str = datetime.datetime.now().strftime("%Y%m%d")
    random_str = ''.join(random.choices(string.ascii_letters + string.digits, k=4))
    domain_name = 'luvvoice.com'
    filename = f"{domain_name}-{date_str}-{random_str}.mp3"
    static_dir = os.path.join('/var/www/fl-tts/static')
    file_path = os.path.join(static_dir, filename)

    await communicate.save(file_path)
    
    # 上传到R2
    public_url = upload_file_to_r2(file_path, filename)
    
    # 删除本地文件，如果你不希望在本地保留副本
    if os.path.exists(file_path):
        os.remove(file_path)

    return "语音合成完成：{}".format(text), public_url


@app.route('/', methods=['GET'])
def index():
    # 只需负责呈现主页面
    return render_template('index.html', languages=languages)


@app.route('/text_to_speech', methods=['POST'])
def handle_text_to_speech():
    # 处理文本到语音转换
    data = request.form
    text = data['text']
    language_code = data['language_code']
    result_text, result_audio_url = anyio.run(text_to_speech_edge, text, language_code)

    # 返回JSON
    return jsonify({
        'result_text': result_text,
        'result_audio_url': result_audio_url,      # 用于播放的URL
    })
    


def upload_file_to_r2(file_path, filename):
    # 猜测文件类型
    content_type, _ = mimetypes.guess_type(file_path)
    if content_type is None:
        # 如果无法确定类型，则设为二进制流
        content_type = 'application/octet-stream'
    
    # 获取文件大小
    file_size = os.path.getsize(file_path)

    # Cloudflare R2的endpoint URL
    r2_endpoint_url = 'https://03686a2ef99b7ed9f35561db0d91af9b.r2.cloudflarestorage.com'
    bucket_name = 'tts'

    # 创建一个Cloudflare R2客户端
    session = boto3.session.Session()
    client = session.client(
        service_name='s3',
        endpoint_url=r2_endpoint_url,
        aws_access_key_id='e528732c80abcd47f037c9d75c936324',
        aws_secret_access_key='a75ded086590daaa83abdb608b7e7b195862282fa01e567f9ca6df2aaa9b0df4',
        config=Config(signature_version='s3v4'),
    )

    

    # 打开文件并上传
    with open(file_path, 'rb') as file:
        client.put_object(
            Bucket=bucket_name,
            Key=filename,
            Body=file,
            ContentType=content_type,
            ContentDisposition=f'attachment; filename="{filename}"',
            ContentLength=file_size
        )

    # 返回文件的URL
    public_url = f"{CLOUDFLARE_R2_BUCKET_URL}/{filename}"
    return public_url



@app.route('/download/<filename>')
def download_audio(filename):
    response = send_from_directory('static', filename, as_attachment=True)
    response.headers["Content-Disposition"] = "attachment; filename={}".format(filename)
    return response


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
