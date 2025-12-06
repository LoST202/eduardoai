Установить зависимости (requirements.txt)
pip install -r requirements.txt
  
Скачать koboldcpp: 
https://github.com/LostRuins/koboldcpp/releases
  
Скачать Модели:
https://huggingface.co/leejet/Z-Image-Turbo-GGUF/resolve/main/z_image_turbo-Q4_0.gguf?download=true - Image Gen Model
https://huggingface.co/koboldcpp/GGUFDumps/resolve/main/flux1vae.safetensors - VAE
https://huggingface.co/unsloth/Qwen3-4B-Instruct-2507-GGUF/resolve/main/Qwen3-4B-Instruct-2507-Q4_K_S.gguf?download=true) - Clip 1
  
Зайти в акккаунт с помощью токена (huggingface cli)
hf auth login

Запустить koboldcpp и загрузить модели во вкладке Image Gen в порядке указанном в пункте Скачать Модели
Запустить main.py и дождаться загрузки моделей зайти по адресу 127.0.0.1:8080
