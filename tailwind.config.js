/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./docs/**/*.html",
    "./docs/page/*.html",
    "./docs/post/*.html"
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
      './docs/**/*.html',
    ],
    option:{
      safelist: [],

    },
    

}


