var argv         = require('minimist')(process.argv.slice(2));
var autoprefixer = require('gulp-autoprefixer');
var chmod        = require('gulp-chmod');
var concat       = require('gulp-concat');
var gulp         = require('gulp');
var gulpif       = require('gulp-if');
var livereload   = require('gulp-livereload');
var plumber      = require('gulp-plumber');
var rename       = require('gulp-rename');
var sass         = require('gulp-sass');
var sourcemaps   = require('gulp-sourcemaps');
var uglify       = require('gulp-uglify');
var cache        = require('gulp-cached');

var enabled = {
    uglify: argv.production,
    maps: argv.production,
    failCheck: argv.production,
    prettyPug: !argv.production,
    cachify: !argv.production
};


/* CSS */
gulp.task('styles', function() {
    gulp.src('src/styles/**/*.sass')
        .pipe(gulpif(enabled.failCheck, plumber()))
        .pipe(gulpif(enabled.maps, sourcemaps.init()))
        .pipe(sass({
            outputStyle: 'compressed'}
            ))
        .pipe(autoprefixer("last 3 versions"))
        .pipe(gulpif(enabled.maps, sourcemaps.write(".")))
        .pipe(gulp.dest('pillar/web/static/assets/css'))
        .pipe(gulpif(argv.livereload, livereload()));
});


/* Simple task for reloading the browser */
gulp.task('reload', function(){
    gulp
        .src('pillar/web/templates/**/*.pug')
        .pipe(gulpif(argv.livereload, livereload()));
});

/* Individual Uglified Scripts */
gulp.task('scripts', function() {
    gulp.src('src/scripts/*.js')
        .pipe(gulpif(enabled.failCheck, plumber()))
        .pipe(gulpif(enabled.cachify, cache('scripting')))
        .pipe(gulpif(enabled.maps, sourcemaps.init()))
        .pipe(gulpif(enabled.uglify, uglify()))
        .pipe(rename({suffix: '.min'}))
        .pipe(gulpif(enabled.maps, sourcemaps.write(".")))
        .pipe(chmod(644))
        .pipe(gulp.dest('pillar/web/static/assets/js/'))
        .pipe(gulpif(argv.livereload, livereload()));
});


/* Collection of scripts in src/scripts/tutti/ to merge into tutti.min.js */
/* Since it's always loaded, it's only for functions that we want site-wide */
gulp.task('scripts_concat_tutti', function() {
    gulp.src('src/scripts/tutti/**/*.js')
        .pipe(gulpif(enabled.failCheck, plumber()))
        .pipe(gulpif(enabled.maps, sourcemaps.init()))
        .pipe(concat("tutti.min.js"))
        .pipe(gulpif(enabled.uglify, uglify()))
        .pipe(gulpif(enabled.maps, sourcemaps.write(".")))
        .pipe(chmod(644))
        .pipe(gulp.dest('pillar/web/static/assets/js/'))
        .pipe(gulpif(argv.livereload, livereload()));
});

gulp.task('scripts_concat_markdown', function() {
    gulp.src('src/scripts/markdown/**/*.js')
        .pipe(gulpif(enabled.failCheck, plumber()))
        .pipe(gulpif(enabled.maps, sourcemaps.init()))
        .pipe(concat("markdown.min.js"))
        .pipe(gulpif(enabled.uglify, uglify()))
        .pipe(gulpif(enabled.maps, sourcemaps.write(".")))
        .pipe(chmod(644))
        .pipe(gulp.dest('pillar/web/static/assets/js/'))
        .pipe(gulpif(argv.livereload, livereload()));
});


// While developing, run 'gulp watch'
gulp.task('watch',function() {
    // Only listen for live reloads if ran with --livereload
    if (argv.livereload){
        livereload.listen();
        // Templates are built via python, we only need to reload the page
        gulp.watch('pillar/web/templates/**/*.pug',['reload']);
    }

    gulp.watch('src/styles/**/*.sass',['styles']);
    gulp.watch('src/scripts/*.js',['scripts']);
    gulp.watch('src/scripts/tutti/**/*.js',['scripts_concat_tutti']);
    gulp.watch('src/scripts/markdown/**/*.js',['scripts_concat_markdown']);
});


// Run 'gulp' to build everything at once
gulp.task('default', ['styles', 'scripts', 'scripts_concat_tutti', 'scripts_concat_markdown']);
