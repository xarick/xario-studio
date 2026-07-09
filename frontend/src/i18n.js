import i18next from "i18next";
import { initReactI18next } from "react-i18next";
import uz from "./locales/uz.json";
import en from "./locales/en.json";
import ru from "./locales/ru.json";

const saved = localStorage.getItem("lang") || "uz";

i18next
  .use(initReactI18next)
  .init({
    resources: { uz: { translation: uz }, en: { translation: en }, ru: { translation: ru } },
    lng: saved,
    fallbackLng: "uz",
    interpolation: { escapeValue: false },
  });

export default i18next;
