import re

with open('D:/AGROBOTAI/server.py', 'r', encoding='utf-8') as f:
    text = f.read()

# Replace the incorrect import and the generate_gradcam logic
new_text = text.replace(
    'from src.gradcam_viz import generate_gradcam',
    'from src.gradcam_viz import generate_gradcam_for_detection, get_target_layer_for_model'
)

new_text = new_text.replace(
    'heatmap_bytes = generate_gradcam(model, img_rgb, is_disease=(target=="disease"))',
    """# Generate heatmap
        # Using standard torchvision pre-processing
        from torchvision import transforms
        import torch
        transform = transforms.Compose([
            transforms.ToPILImage(),
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize([0.485, 0.456, 0.406], [0.229, 0.224, 0.225])
        ])
        
        # Get PyTorch internal model
        pt_model = model.model
        
        # Get target layer
        target_layer = get_target_layer_for_model(pt_model, "convnext_tiny") # The default used in this project
        
        from src.gradcam_viz import GradCAM
        pt_model.eval()
        input_tensor = transform(img_rgb).unsqueeze(0).to("cuda" if torch.cuda.is_available() else "cpu")
        pt_model = pt_model.to("cuda" if torch.cuda.is_available() else "cpu")
        
        gradcam = GradCAM(pt_model, target_layer)
        overlay = gradcam.generate_visualization(img_rgb, input_tensor, alpha=0.6)
        
        _, encoded_img = cv2.imencode('.jpg', cv2.cvtColor(overlay, cv2.COLOR_RGB2BGR))
        heatmap_bytes = encoded_img.tobytes()"""
)

with open('D:/AGROBOTAI/server.py', 'w', encoding='utf-8') as f:
    f.write(new_text)

print("Fixed server.py")
