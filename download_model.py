import urllib.request
import json
import time

print("Starting to pull qwen2.5-coder:7b...")
pull_req = urllib.request.Request(
    'http://localhost:11434/api/pull',
    data=json.dumps({'name': 'qwen2.5-coder:7b', 'stream': False}).encode(),
    headers={'Content-Type': 'application/json'}
)
urllib.request.urlopen(pull_req)
print("Finished pulling!")

print("Copying to qwen3:8b...")
copy_req = urllib.request.Request(
    'http://localhost:11434/api/copy',
    data=json.dumps({'source': 'qwen2.5-coder:7b', 'destination': 'qwen3:8b'}).encode(),
    headers={'Content-Type': 'application/json'}
)
urllib.request.urlopen(copy_req)
print("Finished copying!")
