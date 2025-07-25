import customtkinter
import requests
import os
from PIL import Image, ImageFilter
import threading
import queue

# --- SCRIPT PATH SETUP ---
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_PATH = os.path.join(SCRIPT_DIR, "assets")


# --- Data Fetching in a Separate Thread ---
def get_weather_data(city_name, data_queue):
    """Fetches weather data from OpenWeatherMap API and puts it in a queue."""
    api_key = os.getenv('OPENWEATHER_API_KEY')
    if not api_key:
        error_msg = {"status": "error", "message": "API key not configured."}
        data_queue.put(error_msg)
        return

    url = f'https://api.openweathermap.org/data/2.5/weather?q={city_name}&appid={api_key}&units=metric'

    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            weather_info = {
                "status": "success", "city": data['name'],
                "conditions_desc": data['weather'][0]['description'].title(),
                "conditions_main": data['weather'][0]['main'], "temp": data['main']['temp'],
                "feels_like": data['main']['feels_like'], "humidity": data['main']['humidity'],
                "wind_speed": data['wind']['speed'], "icon": data['weather'][0]['icon']
            }
            data_queue.put(weather_info)
        elif response.status_code == 404:
            data_queue.put({"status": "error", "message": f"City '{city_name}' not found."})
        else:
            data_queue.put({"status": "error", "message": f"API Error (Code: {response.status_code})."})
    except requests.exceptions.RequestException:
        data_queue.put({"status": "error", "message": "Connection error."})


# --- Simple Animation Helper Class ---
class Animation:
    @staticmethod
    def slide_in(widget, start_y, end_y, steps=20, duration_ms=300):
        """Animates a widget's vertical position."""
        delta = (end_y - start_y) / steps
        current_step = 0
        def _animate():
            nonlocal current_step
            current_step += 1
            new_y = start_y + delta * current_step
            widget.place(rely=new_y, relx=0.5, anchor="center")
            if current_step < steps:
                widget.after(duration_ms // steps, _animate)
            else:
                widget.place(rely=end_y, relx=0.5, anchor="center")
        _animate()


# --- Main Application Class ---
class WeatherApp(customtkinter.CTk):
    def __init__(self):
        super().__init__()
        self.title("Glass Weather App")
        self.geometry("400x600")
        self.resizable(False, False)
        customtkinter.set_appearance_mode("dark")

        self.background_map = {
            "Clear_day": "clear_day.png", "Clear_night": "clear_night.png",
            "Clouds_day": "cloudy_day.png", "Clouds_night": "cloudy_night.png",
            "Rain_day": "rainy_day.png", "Rain_night": "rainy_day.png",
            "Drizzle_day": "rainy_day.png", "Drizzle_night": "rainy_day.png",
            "Thunderstorm_day": "stormy_day.png", "Thunderstorm_night": "stormy_day.png",
            "Snow_day": "snowy_day.png", "Snow_night": "snowy_night.png",
            "Mist_day": "cloudy_day.png", "Mist_night": "cloudy_night.png",
        }
        self.current_bg_image = None
        self.data_queue = queue.Queue()

        self.create_widgets()
        self.set_default_appearance()

    def create_widgets(self):
        """Create all widgets once. Their visibility and content will be managed later."""
        self.background_label = customtkinter.CTkLabel(self, text="")
        self.background_label.place(relwidth=1, relheight=1)

        self.glass_border = customtkinter.CTkFrame(self, fg_color="#4a4a4a", corner_radius=22)
        self.glass_panel = customtkinter.CTkLabel(self, text="", corner_radius=20)
        
        search_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        search_frame.place(relx=0.5, rely=0.1, anchor="center", relwidth=0.85)
        
        self.city_entry = customtkinter.CTkEntry(search_frame, placeholder_text="Enter City...", font=("Helvetica", 18), border_width=0, fg_color=("gray90", "gray25"))
        self.city_entry.pack(side="left", fill="x", expand=True, ipady=5, padx=(0, 10))
        self.city_entry.bind("<Return>", self.search_event)

        try:
            search_icon_path = os.path.join(ASSETS_PATH, "icons", "search.png")
            search_icon_image = customtkinter.CTkImage(Image.open(search_icon_path), size=(20, 20))
            self.search_button = customtkinter.CTkButton(search_frame, text="", image=search_icon_image, width=40, fg_color=("gray90", "gray25"), hover_color=("gray80", "gray35"), command=self.search_event)
        except FileNotFoundError:
            self.search_button = customtkinter.CTkButton(search_frame, text="Go", width=50, command=self.search_event)
        self.search_button.pack(side="right")

        self.info_frame = customtkinter.CTkFrame(self, fg_color="transparent")
        
        # --- Widgets inside the info_frame (instantiated but not placed) ---
        self.icon_label = customtkinter.CTkLabel(self.info_frame, text="")
        self.temp_label = customtkinter.CTkLabel(self.info_frame, text="", font=("Helvetica", 64, "bold"))
        self.conditions_label = customtkinter.CTkLabel(self.info_frame, text="", font=("Helvetica", 24, "normal"))
        self.city_label = customtkinter.CTkLabel(self.info_frame, text="", font=("Helvetica", 18, "italic"))
        self.separator = customtkinter.CTkFrame(self.info_frame, height=1, fg_color="gray")
        
        details_frame = customtkinter.CTkFrame(self.info_frame, fg_color="transparent")
        details_frame.grid_columnconfigure((0, 1, 2), weight=1)

        self.feels_label = customtkinter.CTkLabel(details_frame, text="", font=("Helvetica", 14))
        self.feels_label.grid(row=0, column=0, sticky="nsew")
        self.humidity_label = customtkinter.CTkLabel(details_frame, text="", font=("Helvetica", 14))
        self.humidity_label.grid(row=0, column=1, sticky="nsew")
        self.wind_label = customtkinter.CTkLabel(details_frame, text="", font=("Helvetica", 14))
        self.wind_label.grid(row=0, column=2, sticky="nsew")
        self.details_frame = details_frame

        # **FIX:** Create the message label once to be reused for all messages.
        self.message_label = customtkinter.CTkLabel(self, text="", font=("Helvetica", 18), wraplength=300, fg_color=("gray90", "gray20"), corner_radius=20)

    def set_default_appearance(self, message="Search for a city"):
        """Resets the UI to show a message (e.g., for loading or errors)."""
        self.update_background("default.png")
        self.glass_border.place_forget()
        self.glass_panel.place_forget()
        self.info_frame.place_forget()

        # **FIX:** Configure and place the pre-existing message_label.
        self.message_label.configure(text=message)
        self.message_label.place(relx=0.5, rely=0.55, anchor="center", relwidth=0.9, relheight=0.8)
        self.message_label.lift()

    def search_event(self, event=None):
        """Starts the weather data search in a new thread."""
        city = self.city_entry.get()
        if not city:
            self.set_default_appearance("Please enter a city name.")
            return
        
        thread = threading.Thread(target=get_weather_data, args=(city, self.data_queue))
        thread.daemon = True
        thread.start()
        
        self.set_default_appearance("Loading...")
        self.after(100, self.check_data_queue)

    def check_data_queue(self):
        """Checks the queue for data from the worker thread."""
        try:
            data = self.data_queue.get_nowait()
            self.update_ui(data)
        except queue.Empty:
            self.after(100, self.check_data_queue)

    def create_glass_effect(self):
        """Generates and applies the blurred background effect."""
        if self.current_bg_image is None: return
        self.update_idletasks()
        
        panel_w, panel_h = self.glass_panel.winfo_width(), self.glass_panel.winfo_height()
        if panel_w <= 1 or panel_h <= 1:
            self.after(50, self.create_glass_effect)
            return

        panel_x, panel_y = self.glass_panel.winfo_x(), self.glass_panel.winfo_y()
        cropped = self.current_bg_image.crop((panel_x, panel_y, panel_x + panel_w, panel_y + panel_h))
        blurred = cropped.filter(ImageFilter.GaussianBlur(radius=15))
        
        ctk_img = customtkinter.CTkImage(light_image=blurred, dark_image=blurred, size=(panel_w, panel_h))
        self.glass_panel.configure(image=ctk_img)

    def update_background(self, image_name):
        """Updates the main background image."""
        try:
            path = os.path.join(ASSETS_PATH, "backgrounds", image_name)
            win_w, win_h = self.winfo_width(), self.winfo_height()
            if win_w <= 1: # Guard against initial render issues
                return
            self.current_bg_image = Image.open(path).resize((win_w, win_h))
            # **FIX:** Use explicit keyword arguments for clarity.
            bg_img = customtkinter.CTkImage(light_image=self.current_bg_image, dark_image=self.current_bg_image, size=(win_w, win_h))
            self.background_label.configure(image=bg_img)
        except (FileNotFoundError, AttributeError):
            self.current_bg_image = None
            self.background_label.configure(image=None, fg_color="#2B2B2B")

    def update_ui(self, data):
        """Updates the entire UI with new weather data and animations."""
        self.message_label.place_forget()
        self.update_idletasks() 

        if data['status'] == "error":
            self.set_default_appearance(data['message'])
            return

        time_of_day = "day" if data['icon'].endswith('d') else "night"
        condition_key = f"{data['conditions_main']}_{time_of_day}"
        bg_image_name = self.background_map.get(condition_key, "default.png")
        
        self.update_background(bg_image_name)
        
        # Place all background/container elements
        self.glass_border.place(relx=0.5, rely=0.55, anchor="center", relwidth=0.9, relheight=0.8)
        self.glass_panel.place(relx=0.5, rely=0.55, anchor="center", relwidth=0.88, relheight=0.78)
        self.info_frame.place(relx=0.5, rely=0.55, anchor="center", relwidth=0.8, relheight=0.7)
        self.create_glass_effect()

        try:
            icon_path = os.path.join(ASSETS_PATH, "icons", data['icon'] + ".png")
            icon_image = customtkinter.CTkImage(Image.open(icon_path), size=(120, 120))
            self.icon_label.configure(image=icon_image, text="")
        except FileNotFoundError:
            self.icon_label.configure(image=None, text="[Icon?]")

        # Configure text for all labels
        self.temp_label.configure(text=f"{data['temp']:.0f}°")
        self.conditions_label.configure(text=data['conditions_desc'])
        self.city_label.configure(text=data['city'])
        self.feels_label.configure(text=f"Feels Like\n{data['feels_like']:.0f}°")
        self.humidity_label.configure(text=f"Humidity\n{data['humidity']}%")
        self.wind_label.configure(text=f"Wind\n{data['wind_speed']:.1f} m/s")

        # Place static widgets
        self.icon_label.place(relx=0.5, rely=0.22, anchor="center")
        self.city_label.place(relx=0.5, rely=0.65, anchor="center")
        self.separator.place(relx=0.5, rely=0.75, anchor="center", relwidth=0.8)
        self.details_frame.place(relx=0.5, rely=0.86, anchor="center", relwidth=1.0)
        
        self.info_frame.lift()
        
        # Place animated widgets off-screen initially
        self.temp_label.place(rely=1.2, relx=0.5, anchor="center")
        self.conditions_label.place(rely=1.3, relx=0.5, anchor="center")
        
        # Animate them into view
        self.after(100, lambda: Animation.slide_in(self.temp_label, 1.2, 0.45))
        self.after(200, lambda: Animation.slide_in(self.conditions_label, 1.3, 0.55))


if __name__ == "__main__":
    app = WeatherApp()
    app.mainloop()