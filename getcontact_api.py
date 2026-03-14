import time
import os
import base64
import threading
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

app = FastAPI(title="Getcontact REST API Bot")

class GetcontactBot:
    def __init__(self):
        self.driver = None
        self.is_logged_in = False
        self.qr_path = "/home/ubuntu/qr_code.png"
        self.lock = threading.Lock()

    def setup_driver(self):
        if self.driver is None:
            chrome_options = Options()
            chrome_options.add_argument("--headless")
            chrome_options.add_argument("--no-sandbox")
            chrome_options.add_argument("--disable-dev-shm-usage")
            chrome_options.add_argument("--window-size=1920,1080")
            chrome_options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
            
            service = Service("/usr/bin/chromedriver")
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
            print("Tarayıcı başlatıldı.")

    def start_session(self):
        with self.lock:
            self.setup_driver()
            self.driver.get("https://web.getcontact.com")
            try:
                wait = WebDriverWait(self.driver, 20)
                
                # Çerez onayını kabul et
                try:
                    accept_btn = self.driver.find_element(By.XPATH, "//button[contains(text(), 'Accept All')]")
                    accept_btn.click()
                    print("Çerezler kabul edildi.")
                except:
                    pass
                
                qr_container = wait.until(EC.presence_of_element_located((By.CLASS_NAME, "qrcode")))
                time.sleep(3)
                qr_img = qr_container.find_element(By.TAG_NAME, "img")
                qr_img.screenshot(self.qr_path)
                print("Yeni QR kod oluşturuldu.")
                
                # Arka planda giriş kontrolünü başlat
                threading.Thread(target=self.check_login_status, daemon=True).start()
                return True
            except Exception as e:
                print(f"QR kod hatası: {e}")
                return False

    def check_login_status(self):
        print("Giriş durumu kontrol ediliyor...")
        start_time = time.time()
        while time.time() - start_time < 300: # 5 dakika bekleme süresi
            try:
                search_input = self.driver.find_elements(By.NAME, "phoneNumber")
                if len(search_input) > 0:
                    self.is_logged_in = True
                    print("Giriş BAŞARILI!")
                    return
            except:
                pass
            time.sleep(3)
        print("Giriş zaman aşımı.")

    def search_gsm(self, number):
        if not self.is_logged_in:
            return {"error": "Önce giriş yapmalısınız (/qr-code)"}
        
        with self.lock:
            try:
                # Sayfayı yenile veya ana sayfaya git
                self.driver.get("https://web.getcontact.com")
                wait = WebDriverWait(self.driver, 15)
                
                # Arama kutusunu bekle
                search_input = wait.until(EC.presence_of_element_located((By.NAME, "phoneNumber")))
                search_input.clear()
                search_input.send_keys(number)
                
                # Arama butonunu bul ve tıkla
                submit_btn = self.driver.find_element(By.ID, "submitButton")
                submit_btn.click()
                
                # Sonuçların yüklenmesini bekle (rpb-card sınıfı sonuç geldiğini gösterir)
                wait.until(EC.presence_of_element_located((By.CLASS_NAME, "rpb-card")))
                time.sleep(2)
                
                name = self.driver.find_element(By.CSS_SELECTOR, ".rpbi-info h1").text.strip()
                operator = self.driver.find_element(By.CSS_SELECTOR, ".rpbi-info em").text.strip()
                
                return {"status": "success", "number": number, "name": name, "operator": operator}
            except Exception as e:
                self.driver.save_screenshot("/home/ubuntu/search_error.png")
                return {"status": "error", "message": f"Sorgu hatası: {str(e)}"}

bot = GetcontactBot()

@app.get("/qr-code")
async def get_qr():
    success = bot.start_session()
    if success:
        return FileResponse(bot.qr_path)
    raise HTTPException(status_code=500, detail="QR kod oluşturulamadı")

@app.get("/gsm/{number}")
async def search(number: str):
    # Başındaki +90 veya 0'ı temizle (isteğe bağlı, siz 534... formatında istediniz)
    clean_number = number[-10:] 
    result = bot.search_gsm(clean_number)
    return result

@app.get("/durum")
async def status():
    return {
        "giris_yapildi": bot.is_logged_in,
        "mesaj": "Hesaba giriş yapıldı" if bot.is_logged_in else "Giriş bekleniyor veya QR kod okutulmadı"
    }

# FastAPI uygulamasını dışarıdan çalıştırmak için
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
