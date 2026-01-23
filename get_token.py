from html_telegraph_poster import TelegraphPoster

t = TelegraphPoster(use_api=True)
# 创建一个名为 MyRSSBot 的账号
account = t.create_api_token('MyRSSBot', 'MyRSSBot')
print("\n" + "="*30)
print("你的 Telegraph Token 是:")
print(account['access_token'])
print("="*30 + "\n")
