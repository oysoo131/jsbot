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
vc_channel = None
plrid = {}
cm = {}

intents = discord.Intents.all()
client = discord.Client(intents=intents)
tree = discord.app_commands.CommandTree(client=client)

# ----------------------------- 웹훅 서버 -----------------------------
@routes.post('/roblox')
async def roblox_webhook(request):
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
    app = web.Application()
    app.add_routes(routes)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8080)
    await site.start()
    print("웹 서버 실행 중: http://0.0.0.0:8080")

# ------------------------- Roblox Publish -------------------------
UNIVERSE_ID = "8174334681"
TOPIC = "nsotp"

async def publish_message(args):
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

# --------------------- 대기 함수 ---------------------
async def wait_for_cs_key_true(argm, timeout=3):
    cs[argm] = False
    start = asyncio.get_event_loop().time()
    while not cs[argm]:
        if asyncio.get_event_loop().time() - start > timeout:
            return False
        await asyncio.sleep(0.05)
    return True

# ----------------------- Modals -----------------------
class OTPModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="OTP 인증")
        self.user_input = discord.ui.TextInput(label="게임에서 표시된 OTP 코드를 입력하세요")
        self.add_item(self.user_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        await publish_message(self.user_input.value)
        msg = await wait_for_cs_key_true(plrid[interaction.user.id])
        if msg:
            await interaction.followup.send("연동 성공!")
            conn = sqlite3.connect("maindb.db")
            cur = conn.cursor()
            data_bytes = pickle.dumps({"v": plrid[interaction.user.id]})
            cur.execute("INSERT OR REPLACE INTO Datas (UUID, data) VALUES (?, ?)", (interaction.user.id, data_bytes))
            conn.commit()
            conn.close()
        else:
            await interaction.followup.send("인증코드가 일치하지 않습니다.")

class IDInputModal(discord.ui.Modal):
    def __init__(self):
        super().__init__(title="ID 입력")
        self.user_input = discord.ui.TextInput(label="Roblox 닉네임(디스플레이 X)", placeholder="정확한 Roblox 닉네임")
        self.add_item(self.user_input)

    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer()
        value = self.user_input.value
        plrid[interaction.user.id] = value

        view = discord.ui.View()
        view.add_item(discord.ui.Button(label="인증맵", style=discord.ButtonStyle.link, url="https://www.roblox.com/games/71952469178723/unnamed"))
        btn_input = discord.ui.Button(label="OTP 입력", style=discord.ButtonStyle.green)

        async def btn_callback(intx):
            await intx.response.send_modal(OTPModal())

        btn_input.callback = btn_callback
        view.add_item(btn_input)

        await cm[interaction.user.id].edit(
            content=f"{value} 님, 인증맵에서 OTP를 받으신 뒤 'OTP 입력'을 눌러 연동을 완료해주세요.",
            view=view
        )

# ------------------------ 인증 버튼 ------------------------
class VerificationView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        btn = discord.ui.Button(label="인증하기", style=discord.ButtonStyle.green)
        btn.callback = self.button_callback
        self.add_item(btn)

    async def button_callback(self, interaction: discord.Interaction):
        await interaction.response.defer()
        conn = sqlite3.connect("./maindb.db")
        cur = conn.cursor()
        cur.execute("SELECT * FROM Datas WHERE UUID = ?", (interaction.user.id,))
        row = cur.fetchone()
        cur.close()
        conn.close()

        if row:
            data_dict = pickle.loads(row[1])
            await interaction.user.edit(nick="@" + data_dict.get("v", "Error"))
            if role:
                await interaction.user.add_roles(role)
            await interaction.followup.send("이미 연동된 계정입니다. 역할과 닉네임을 업데이트했습니다.")
        else:
            dm = await interaction.user.create_dm()
            modal_view = discord.ui.View()
            btn = discord.ui.Button(label="연동하기", style=discord.ButtonStyle.green)

            async def btn_callback_dm(intx):
                await intx.response.send_modal(IDInputModal())

            btn.callback = btn_callback_dm
            modal_view.add_item(btn)
            msg = await dm.send("농사시뮬레이터 서버에 연동된 계정이 없습니다. 아래 '연동하기' 버튼을 눌러 연동하세요.", view=modal_view)
            cm[interaction.user.id] = msg

# ------------------------ Slash Commands ------------------------
@tree.command(name="인증_메시지_전송", description="인증 버튼 메시지를 인증 채널에 전송합니다.")
async def send_verification_message(interaction: discord.Interaction, msg: str):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("관리자만 실행 가능합니다.", ephemeral=True)
        return

    global vc_channel
    if vc_channel is None:
        await interaction.response.send_message("인증 채널이 설정되어 있지 않습니다.", ephemeral=True)
        return

    view = VerificationView()
    await vc_channel.send(msg, view=view)
    await interaction.response.send_message("인증 메시지를 전송했습니다.", ephemeral=True)

@tree.command(name="인증_채널_설정", description="인증 채널을 설정합니다.")
async def set_verification_channel(interaction: discord.Interaction, channel: discord.TextChannel):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("관리자만 실행 가능합니다.", ephemeral=True)
        return
    global vc_channel
    vc_channel = channel
    await interaction.response.send_message(f"인증 채널이 {channel.mention} 으로 설정되었습니다.", ephemeral=True)

@tree.command(name="인증_역할_설정", description="인증 역할을 설정합니다.")
async def set_verification_role(interaction: discord.Interaction, rolea: discord.Role):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("관리자만 실행 가능합니다.", ephemeral=True)
        return
    global role
    role = rolea
    await interaction.response.send_message(f"인증 역할이 {rolea.mention} 으로 설정되었습니다.", ephemeral=True)

# ------------------------ 봇 실행 ------------------------
@client.event
async def on_ready():
    print(f"✅ 봇 로그인 완료: {client.user} | IP: {requests.get('https://ipinfo.io/ip').text.strip()}")
    await tree.sync()
    client.loop.create_task(start_web_app())
    await client.change_presence(status=discord.Status.idle, activity=discord.CustomActivity("🤍 농사시뮬레이터 인증 관리 중 🤍"))

    # Persistent View 등록
    client.add_view(VerificationView())
    print("✅ Persistent View 등록 완료")

client.run(TOKEN)
