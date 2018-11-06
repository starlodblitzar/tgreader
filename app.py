from tornado.ioloop import IOLoop
from tornado.web import Application, RequestHandler
from tornado.httputil import HTTPServerRequest

from pyrogram import Client
from pyrogram.api.functions.messages import GetDialogs
from pyrogram.api.types import Chat, ChannelForbidden, Channel, ChatForbidden, ChatEmpty, Message
from pyrogram.api.types.messages import Dialogs

from logging import getLogger, Formatter, DEBUG
from logging.handlers import TimedRotatingFileHandler
from json import dumps, loads
from requests import post, Response
from typing import Optional, List, Union
from os import remove


# setup logger
LOG = getLogger(__name__)
LOG.setLevel(DEBUG)
file_handler = TimedRotatingFileHandler('log.log', when="midnight")
file_handler.setLevel(DEBUG)
formatter = Formatter('%(asctime)s - %(name)-5s - %(levelname)-5s - %(message)s')
file_handler.setFormatter(formatter)
LOG.addHandler(file_handler)

IMGUR_ID: str = '7a2220c5364bd22'
IMGUR_URL: str = 'https://api.imgur.com/3/image'
TG_ID: str = '203770'
TG_HASH: str = '6ba87d57df603d3b8b9e4617070d9a64'
BANNED_CHANNELS: List[str] = [
    'Бот',
    'trade-mate.io marketing',
    'Криптекс Маркетинг',
    'trade-mate.io marketing elena'
]

try:
    tg_app: Client = Client(
        session_name='telegram',
        api_id=TG_ID,
        api_hash=TG_HASH
    )
    tg_app.start()

    LOG.info('Successfully initialized telegram client')

except Exception as e:
    LOG.error('Failed to initialize telegram client with the following error: {}'.format(str(e)))



def save_image(image_path: str) -> Optional[str]:
    headers: dict = {
        'Authorization': "Client-ID {}".format(IMGUR_ID)
    }

    with open(image_path, 'rb') as image_file:
        files: dict = {
            'image': image_file.read()
        }

    try:
        LOG.info('Sending request to imgur with the following params to acquire image link: {}'.format({
            'headers': headers,
            'files': files
        }))
        response: Response = post(url=IMGUR_URL, files=files, headers=headers)

        LOG.info('Received the following response from imgur: {}'.format(response.text))

        return loads(response.text)['data']['link']

    except Exception as e:
        LOG.error("Failed to acquire link for photo in message with the following error {}".format(e))

        return None


class ChannelHandler(RequestHandler):
    def __init__(self, application: Application, request: HTTPServerRequest):
        super().__init__(application, request)

        LOG.info('Got channels request: {request}'.format(request=request))

    def get(self) -> None:
        response: dict = dict()
        dialogs: Optional[Dialogs] = None

        LOG.info('Sending request for contacts to telegram to get list of dialogs')

        try:
            print("""DIALOGS""")
            dialogs = tg_app.get_dialogs()
            print(dialogs)
            print("""END DIALOGS""")

            # LOG.info('Got the following list of dialogs: {}'.format(dialogs))

        except Exception as e:
            LOG.error('Failed to get response from telegram with the following error: {}'.format(e))

            response.update({'success': False})

            self.write(dumps(response))
            self.flush()

        # if dialogs:
        #     # payload: List[str, Union[ChatEmpty, Chat, Channel]] = [{
        #     #     'id': elem.id,
        #     #     'name': elem.title,
        #     #     'type': (lambda x: 'CHANNEL' if type(x) == Channel else 'CHAT')(elem)
        #     # } for elem in dialogs]
        #
        #     for elem in dialogs:
        #         print(type(elem))
        #         print(elem)


            # response.update({
            #     "success": True,
            #     "data": payload
            # })

            self.write(dumps(response))

        LOG.info('Sending response for channels request: {}'.format(response))

        self.flush()

@tg_app.on_message()
def message_handler(app, message: Message) -> None:

    chanel_types: List[str] = ['channel', 'supergroup']
    group_types: List[str] = ['group']

    payload: dict = dict()

    if message.chat.type in chanel_types + group_types and message.chat.title not in BANNED_CHANNELS:
        channel_id: Optional[str] = None

        if message.chat.type == 'channel' or message.chat.type == 'supergroup':
            channel_id = int(str(message.chat.id)[3:])

        elif message.chat.type == 'group':
            channel_id = int(message.chat.id) * (-1)

        LOG.info('Got the following message from channel {} with telegram_id {} and timestamp {}'.format(
                str(message.chat.title).encode('utf-8'),
                channel_id,
                message.date)
        )

        LOG.info("Message content: {}".format(message))

        payload.update({
            'channel_id': channel_id,
            'time': message.date,
            'message_id': message.message_id,
            'message': None
        })

        if message.text:
            payload.update({
                'message': message.text
            })

        if message.photo:
            LOG.info('Handling image')

            if not message.text:
                payload.update({
                    'message': ''
                })

            if message.caption:
                payload['message'] += message.caption

            try:
                img_path: str = tg_app.download_media(message)

                img_link: str = save_image(img_path)

                # delete image from local
                remove(img_path)

                if img_link:
                    payload['message'] += '::::image_link::{}::::'.format(img_link)

            except Exception as e:
                LOG.error('Failed to save image with the following error: {}'.format(e))

        if payload['message'] is not None:
            LOG.info('Sending the following payload to the server: {}'.format(str(payload).encode('utf-8')))

            try:
                response = post('http://alterspace.info:9091/api/telegram/messages', dumps(payload))
                LOG.info('Got the following response: status_code: {}, text: {}'.format(response.status_code,
                                                                                            response.text))
            except Exception as e:
                LOG.error('Failed to send message with the following error: {}'.format(str(e)))

        else:
            LOG.info('Got message without image or text. Not sending to the server')


if __name__ == "__main__":
    app: Application = Application([
        (r'/channels', ChannelHandler)
    ])
    app.listen(port=9001, address='0.0.0.0')
    LOG.info('App inited.')
    IOLoop.current().start()