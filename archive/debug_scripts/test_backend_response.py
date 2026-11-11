import requests

# Test with a sample image
img_path = 'data/tomato-septoria-leaf-spot-closeup.jpg'

print('Uploading image to /api/analyze...')

# Use FormData approach matching frontend
with open(img_path, 'rb') as f:
    files = {'file': ('test.jpg', f, 'image/jpeg')}
    data = {'crop': 'Tomato', 'cri_variant': 'CRI1', 'api_key': ''}
    response = requests.post(
        'http://localhost:8000/api/analyze',
        files=files,
        data=data,
        timeout=120
    )

print(f'Status: {response.status_code}')
if response.status_code == 200:
    result = response.json()
    print('\n=== RESPONSE STRUCTURE ===')
    print(f'Keys in response: {list(result.keys())}')

    # Check critical fields that App.jsx accesses
    print('\n=== CRITICAL FIELD CHECKS ===')
    print(f'result.severity exists: {"severity" in result}')
    if 'severity' in result:
        print(f'  severity keys: {list(result["severity"].keys()) if result["severity"] else "NULL"}')
        print(f'  affected_percentage: {result["severity"].get("affected_percentage")}')
        print(f'  healthy_percentage: {result["severity"].get("healthy_percentage")}')
        print(f'  severity_stage: {result["severity"].get("severity_stage")}')
        print(f'  severity_score: {result["severity"].get("severity_score")}')

    print(f'\nresult.nutrients exists: {"nutrients" in result}')
    if 'nutrients' in result:
        print(f'  nutrients keys: {list(result["nutrients"].keys()) if result["nutrients"] else "NULL"}')
        print(f'  primary_deficiency: {result["nutrients"].get("primary_deficiency")}')
        print(f'  has_deficiency: {result["nutrients"].get("has_deficiency")}')
        print(f'  affected_leaf_zone: {result["nutrients"].get("affected_leaf_zone")}')
        print(f'  severity: {result["nutrients"].get("severity")}')

    print(f'\nresult.pest exists: {"pest" in result}')
    if 'pest' in result:
        print(f'  pest: {result["pest"]}')

    print(f'\nresult.disease exists: {"disease" in result}')
    if 'disease' in result:
        print(f'  disease: {result["disease"]}')

    print(f'\nresult.ndre exists: {"ndre" in result}')
    print(f'result.cri exists: {"cri" in result}')
    print(f'result.overall exists: {"overall" in result}')
    print(f'result.advice exists: {"advice" in result}')

    # Check if heatmaps are present
    print('\n=== HEATMAP CHECKS ===')
    if 'severity' in result and result['severity']:
        print(f'severity.visual_map_base64 present: {"visual_map_base64" in result["severity"]}')
    if 'ndre' in result and result['ndre']:
        print(f'ndre.heatmap_base64 present: {"heatmap_base64" in result["ndre"]}')
    if 'cri' in result and result['cri']:
        print(f'cri.heatmap_base64 present: {"heatmap_base64" in result["cri"]}')

    print('\n✅ Backend response is valid')
else:
    print(f'❌ Error: {response.text}')
