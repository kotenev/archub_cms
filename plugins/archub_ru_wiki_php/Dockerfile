FROM php:8.4-cli-alpine

WORKDIR /app

COPY composer.json ./
COPY public ./public
COPY src ./src
COPY plugin.json README.md ./

RUN apk add --no-cache git unzip sqlite-libs \
    && php -r "copy('https://getcomposer.org/installer', 'composer-setup.php');" \
    && php composer-setup.php --install-dir=/usr/local/bin --filename=composer \
    && rm composer-setup.php \
    && composer install --no-dev --prefer-dist --no-interaction --optimize-autoloader

EXPOSE 8097

CMD ["php", "-S", "0.0.0.0:8097", "-t", "public"]
