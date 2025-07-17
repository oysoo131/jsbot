import discord
import sqlite3
import pickle
import aiohttp
import asyncio
import requests
from aiohttp import web
import json
from dotenv import load_dotenv
import os

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
TOKEN2 = os.getenv("TOEKN")
routes = web.RouteTableDef()
cs = {}
role = None

@routes.post('/roblox')
async def roblox_webhook(request):
    print(request)
    if request.content_type != 'application/json':
        return web.Response(text="Content-Type must be application/json", status=400)

    try:
        body = await request.text()
        if not body.strip():
            return web.Response(text="Empty body", status=400)
        data = json.loads(body)
    except Exception as e:
        print(f"JSON 파싱 실패: {e}")
        return web.Response(text=f"Invalid JSON: {e}", status=400)

    cs[data] = True
    return web.Response(text="OK")

async def start_web_app():
    try:
        app = web.Application()
        app.add_routes(routes)
        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, '0.0.0.0', 8080)
        await site.start()
        print("웹 서버 실행 중: http://0.0.0.0:8080")
    except Exception as e:
        print(f"웹 서버 실행 실패: {e}")

plrid = {}
vc_channel = None
cm = {}

async def wait_for_cs_key_true(argm, timeout=3):
    try:
        cs[argm] = False
        start = asyncio.get_event_loop().time()
        while not cs[argm]:
            if asyncio.get_event_loop().time() - start > timeout:
                return False
            await asyncio.sleep(0.05)
        return True
    except Exception as e:
        print(f"wait_for_cs_key_true 에러: {e}")
        return False

async def button_callback(button_interaction: discord.Interaction):
    try:
        await button_interaction.response.defer()
        with sqlite3.connect("./maindb.db") as conn:
            cur = conn.cursor()
            cur.execute("SELECT * FROM Datas WHERE UUID = ?", (button_interaction.user.id,))
            row = cur.fetchone()

            if row:
                data_dict = pickle.loads(row[1])
                await button_interaction.user.edit(nick="@" + data_dict.get("v", "Error"))
                if role:
                    await button_interaction.user.add_roles(role)
            else:
                async def bc(int: discord.Interaction):
                    try:
                        modal = IDInput()
                        await int.response.send_modal(modal)
                    except Exception as e:
                        print(f"bc 에러: {e}")

                dm_channel = await button_interaction.user.create_dm()
                v = discord.ui.View(timeout=None)
                btn = discord.ui.Button(label="연동하기", style=discord.ButtonStyle.green)
                btn.callback = bc
                v.add_item(btn)

                cm[button_interaction.user.id] = await dm_channel.send(
                    "농사시뮬레이터 서버에 인증된 계정이 없으십니다! 아래의 연동하기를 눌러 연동하세요!", view=v
                )
    except Exception as e:
        print(f"button_callback 에러: {e}")

UNIVERSE_ID = "8174334681"
TOPIC = "nsotp"

async def publish_message(args):
    try:
        url = f"https://apis.roblox.com/cloud/v2/universes/{UNIVERSE_ID}:publishMessage"
        headers = {
            "x-api-key": TOKEN2,
            "Content-Type": "application/json"
        }
        json_data = {
            "topic": TOPIC,
            "message": args
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, headers=headers, json=json_data) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    print("메시지 전송 성공:", data)
                else:
                    text = await resp.text()
                    print(f"실패: 상태 코드 {resp.status}, 응답: {text}")
    except Exception as e:
        print(f"publish_message 에러: {e}")

intents = discord.Intents.all()
client = discord.Client(intents=intents)
tree = discord.app_commands.CommandTree(client=client)

class otpcomp(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="otp인증")
        self.user_input = discord.ui.TextInput(
            label="otp코드를 입력해주세요", placeholder="게임에 들어가면 화면에 나옵니다!"
        )
        self.add_item(self.user_input)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer()
            await publish_message(self.user_input.value)
            msg = await wait_for_cs_key_true(plrid.get(interaction.user.id, ""), timeout=5)
            if msg:
                await interaction.followup.send("연동성공!")
                with sqlite3.connect("maindb.db") as conn:
                    cur = conn.cursor()
                    data_bytes = pickle.dumps({"v": plrid.get(interaction.user.id, "")})
                    cur.execute(
                        "INSERT OR REPLACE INTO Datas (UUID, data) VALUES (?, ?)",
                        (interaction.user.id, data_bytes)
                    )
                    conn.commit()
            else:
                await interaction.followup.send("인증코드가 일치하지 않습니다")
        except Exception as e:
            print(f"otpcomp on_submit 에러: {e}")

class IDInput(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="id입력")
        self.user_input = discord.ui.TextInput(
            label="id를 입력해주세요", placeholder="id 디스플레이딕 말고 진짜 닉네임으로!!!"
        )
        self.add_item(self.user_input)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            await interaction.response.defer()
            value = self.user_input.value
            plrid[interaction.user.id] = value
            v = discord.ui.View()
            btn = discord.ui.Button(
                label="인증맵", style=discord.ButtonStyle.green,
                url="https://www.roblox.com/ko/games/71952469178723/unnamed"
            )
            btn2 = discord.ui.Button(label="입력", style=discord.ButtonStyle.gray)

            async def b2ck(int):
                try:
                    modal = otpcomp()
                    await int.response.send_modal(modal)
                except Exception as e:
                    print(f"b2ck 에러: {e}")

            btn2.callback = b2ck
            v.add_item(btn)
            v.add_item(btn2)
            await cm[interaction.user.id].edit(
                content=f"id가 확인되었습니다! 반갑습니다 {value}님! 아래의 인증맵을 눌러 인증코드를 받으시고 옆의 입력 버튼을 눌러 인증을 완료하세요",
                view=v
            )
        except Exception as e:
            print(f"IDInput on_submit 에러: {e}")

@tree.command(name="인게임_정보_확인", description="인 게임의 정보를 확인 합니다!")
async def ingame_info(interaction: discord.Interaction):
    try:
        await interaction.response.send_message("아직 미완성이에요 헤헤")
    except Exception as e:
        print(f"ingame_info 에러: {e}")

@tree.command(name="인증_채널_설정", description="디코 인증 채널을 설정합니다!")
async def set_verification_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    try:
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("인증 채널 설정 실패! 관리자가 아닙니다.")
            return
        global vc_channel
        vc_channel = channel
        await interaction.response.send_message(f"인증 채널 설정 완료: {channel.mention}")
    except Exception as e:
        print(f"set_verification_channel 에러: {e}")

@tree.command(name="인증_역할_설정", description="디코 인증 역할을 설정합니다!")
async def set_verification_role(interaction: discord.Interaction, rolea: discord.Role):
    try:
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("인증 역할 설정 실패! 관리자가 아닙니다.")
            return
        global role
        role = rolea
        await interaction.response.send_message(f"인증 역할 설정 완료: {rolea.mention}")
    except Exception as e:
        print(f"set_verification_role 에러: {e}")

@tree.command(name="인증_메시지_전송", description="디코 인증 메시지를 전송합니다!")
async def send_verification_message(interaction: discord.Interaction, msg: str):
    try:
        await interaction.response.defer(thinking=True)
        global vc_channel
        if vc_channel is None or not interaction.user.guild_permissions.administrator:
            await interaction.followup.send("인증 채널이 없거나 권한이 없습니다!")
            return
        view = discord.ui.View(timeout=None)
        button = discord.ui.Button(style=discord.ButtonStyle.green, label="인증하기")
        button.callback = button_callback
        view.add_item(button)
        await vc_channel.send(msg, view=view)
        await interaction.followup.send("인증 메시지 전송 완료!")
    except Exception as e:
        print(f"send_verification_message 에러: {e}")

@client.event
async def on_ready():
    try:
        ip = requests.get('https://ipinfo.io/ip', timeout=5).text.strip()
        print(f"관리봇 로그인 완료! {client.user} ip:{ip}")
    except Exception as e:
        print(f"IP 확인 실패: {e}")
    client.loop.create_task(start_web_app())
    await client.change_presence(status=discord.Status.idle, activity=discord.CustomActivity("🤍농심 디코 서버 관리 중🤍"))
    try:
        await tree.sync()
    except Exception as e:
        print(f"명령어 동기화 실패: {e}")

# Persistent View 등록
persistent_view = discord.ui.View(timeout=None)
persistent_button = discord.ui.Button(style=discord.ButtonStyle.green, label="인증하기")
persistent_button.callback = button_callback
persistent_view.add_item(persistent_button)
client.add_view(persistent_view)

client.run(TOKEN)
