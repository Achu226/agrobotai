with open('D:/AGROBOTAI/app.py', 'r', encoding='utf-8') as f:
    text = f.read()
text = text.replace('🌱', '')
text = text.replace('🚀', '')
text = text.replace('📍', '')
text = text.replace('📄', '')
text = text.replace('💡', '')
with open('D:/AGROBOTAI/app.py', 'w', encoding='utf-8') as f:
    f.write(text)
