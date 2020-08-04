./node_modules/.bin/sass --style=compressed busstops/static/css/style.scss busstops/static/css/style.css

./node_modules/.bin/postcss busstops/static/css/style.css --map=false --use=autoprefixer -o busstops/static/css/style.css

./node_modules/.bin/sass --style=compressed busstops/static/css/ie.scss busstops/static/css/ie.css

