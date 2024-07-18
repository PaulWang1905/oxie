/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./html/**/*.html",
    "./html/page/*.html",
    "./html/post/*.html"
  ],
  theme: {
    extend: {},
  },
  plugins: [
  require('daisyui'),
  require("@tailwindcss/typography"),
  ],
  daisyui: {
    themes: ["winter","light","dark"], // Add this line to include the retro theme
  },
  //purge: {
	  content: [
      './html/**/*.html',
    ],
    option:{
      safelist: [],

    },
    

}


