document.addEventListener('DOMContentLoaded', () => {
    Telegram.WebApp.ready();
    Telegram.WebApp.expand();
    Telegram.WebApp.BackButton.show();
    Telegram.WebApp.BackButton.onClick(() => {
        window.location.href = '/';
    });
});

function adjustBet(amount) {
    const betInput = document.getElementById('bet');
    let currentBet = parseInt(betInput.value) || 1000;
    currentBet = Math.max(100, currentBet + amount);
    betInput.value = currentBet;
}

async function playSlots() {
    const bet = document.getElementById('bet').value;
    const resultDiv = document.getElementById('game-result');
    const errorDiv = document.getElementById('error-message');
    resultDiv.innerHTML = '';
    errorDiv.innerHTML = '';
    Telegram.WebApp.MainButton.setText('Крутим...').show();
    try {
        const response = await fetch('/slots', {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: `bet=${bet}`
        });
        const data = await response.json();
        if (data.error) {
            errorDiv.innerHTML = data.error;
        } else {
            resultDiv.innerHTML = `${data.result}<br>${data.message}<br>Баланс: ${data.balance}`;
        }
    } catch (error) {
        errorDiv.innerHTML = 'Ошибка при игре!';
    }
    Telegram.WebApp.MainButton.hide();
}

async function playRoulette(betType) {
    const bet = document.getElementById('bet').value;
    const resultDiv = document.getElementById('game-result');
    const errorDiv = document.getElementById('error-message');
    resultDiv.innerHTML = '';
    errorDiv.innerHTML = '';
    Telegram.WebApp.MainButton.setText('Крутим...').show();
    try {
        const response = await fetch('/roulette', {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: `bet=${bet}&bet_type=${betType}`
        });
        const data = await response.json();
        if (data.error) {
            errorDiv.innerHTML = data.error;
        } else {
            resultDiv.innerHTML = `Результат: ${data.result}<br>${data.message}<br>Баланс: ${data.balance}`;
        }
    } catch (error) {
        errorDiv.innerHTML = 'Ошибка при игре!';
    }
    Telegram.WebApp.MainButton.hide();
}

async function playRocket() {
    const bet = document.getElementById('bet').value;
    const resultDiv = document.getElementById('game-result');
    const errorDiv = document.getElementById('error-message');
    resultDiv.innerHTML = '';
    errorDiv.innerHTML = '';
    Telegram.WebApp.MainButton.setText('Старт').show();
    Telegram.WebApp.MainButton.onClick(async () => {
        try {
            const response = await fetch('/rocket', {
                method: 'POST',
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                body: `bet=${bet}&action=start`
            });
            const data = await response.json();
            if (data.error) {
                errorDiv.innerHTML = data.error;
                Telegram.WebApp.MainButton.hide();
                return;
            }
            resultDiv.innerHTML = `Ракета летит! Коэффициент: x${data.coef.toFixed(2)}`;
            Telegram.WebApp.MainButton.setText('Кэшаут').show();
            Telegram.WebApp.MainButton.onClick(cashoutRocket);
            const interval = setInterval(async () => {
                const checkResponse = await fetch('/rocket', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                    body: 'action=check'
                });
                const checkData = await checkResponse.json();
                if (checkData.crashed) {
                    clearInterval(interval);
                    resultDiv.innerHTML = `Ракета разбилась на x${checkData.coef.toFixed(2)}!<br>Баланс: ${checkData.balance}`;
                    Telegram.WebApp.MainButton.hide();
                } else {
                    resultDiv.innerHTML = `Ракета летит! Коэффициент: x${checkData.coef.toFixed(2)}`;
                }
            }, 500);
        } catch (error) {
            errorDiv.innerHTML = 'Ошибка при игре!';
            Telegram.WebApp.MainButton.hide();
        }
    });
}

async function cashoutRocket() {
    const resultDiv = document.getElementById('game-result');
    const errorDiv = document.getElementById('error-message');
    try {
        const response = await fetch('/rocket', {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: 'action=cashout'
        });
        const data = await response.json();
        if (data.error) {
            errorDiv.innerHTML = data.error;
        } else {
            resultDiv.innerHTML = `${data.message}<br>Баланс: ${data.balance}`;
        }
    } catch (error) {
        errorDiv.innerHTML = 'Ошибка при кэшауте!';
    }
    Telegram.WebApp.MainButton.hide();
}

async function playBlackjack(action) {
    const bet = document.getElementById('bet').value;
    const resultDiv = document.getElementById('game-result');
    const errorDiv = document.getElementById('error-message');
    resultDiv.innerHTML = '';
    errorDiv.innerHTML = '';
    if (action === 'start') {
        Telegram.WebApp.MainButton.setText('Старт').show();
    }
    try {
        const response = await fetch('/blackjack', {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: `bet=${bet}&action=${action}`
        });
        const data = await response.json();
        if (data.error) {
            errorDiv.innerHTML = data.error;
            Telegram.WebApp.MainButton.hide();
        } else {
            resultDiv.innerHTML = `Ваши карты: ${data.player_cards} (Сумма: ${data.player_sum})<br>` +
                                  `Карты дилера: ${data.dealer_cards}<br>${data.message}` +
                                  (data.balance ? `<br>Баланс: ${data.balance}` : '');
            if (data.message.includes('победил') || data.message.includes('Ничья') || data.message.includes('Перебор')) {
                Telegram.WebApp.MainButton.hide();
            }
        }
    } catch (error) {
        errorDiv.innerHTML = 'Ошибка при игре!';
        Telegram.WebApp.MainButton.hide();
    }
}

async function playDice() {
    const bet = document.getElementById('bet').value;
    const resultDiv = document.getElementById('game-result');
    const errorDiv = document.getElementById('error-message');
    resultDiv.innerHTML = '';
    errorDiv.innerHTML = '';
    Telegram.WebApp.MainButton.setText('Бросить').show();
    try {
        const response = await fetch('/dice', {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: `bet=${bet}`
        });
        const data = await response.json();
        if (data.error) {
            errorDiv.innerHTML = data.error;
        } else {
            resultDiv.innerHTML = `Ваши кости: ${data.player_dice.join(' + ')} = ${data.player_sum}<br>` +
                                  `Кости бота: ${data.bot_dice.join(' + ')} = ${data.bot_sum}<br>` +
                                  `${data.message}<br>Баланс: ${data.balance}`;
        }
    } catch (error) {
        errorDiv.innerHTML = 'Ошибка при игре!';
    }
    Telegram.WebApp.MainButton.hide();
}

async function claimBonus() {
    const resultDiv = document.getElementById('game-result');
    const errorDiv = document.getElementById('error-message');
    resultDiv.innerHTML = '';
    errorDiv.innerHTML = '';
    try {
        const response = await fetch('/bonus', {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
        });
        const data = await response.json();
        if (data.error) {
            errorDiv.innerHTML = data.error;
        } else {
            resultDiv.innerHTML = `${data.message}<br>Баланс: ${data.balance}`;
        }
    } catch (error) {
        errorDiv.innerHTML = 'Ошибка при получении бонуса!';
    }
}

async function adminAction(action, targetId, amount) {
    const resultDiv = document.getElementById('game-result');
    const errorDiv = document.getElementById('error-message');
    resultDiv.innerHTML = '';
    errorDiv.innerHTML = '';
    try {
        const response = await fetch('/admin', {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: `action=${action}&target_id=${targetId}&amount=${amount || ''}`
        });
        const data = await response.json();
        if (data.error) {
            errorDiv.innerHTML = data.error;
        } else {
            resultDiv.innerHTML = data.message;
        }
    } catch (error) {
        errorDiv.innerHTML = 'Ошибка при выполнении действия!';
    }
}

async function sendBroadcast() {
    const message = document.getElementById('broadcast-message').value;
    const resultDiv = document.getElementById('game-result');
    const errorDiv = document.getElementById('error-message');
    resultDiv.innerHTML = '';
    errorDiv.innerHTML = '';
    try {
        const response = await fetch('/broadcast', {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: `message=${encodeURIComponent(message)}`
        });
        const data = await response.json();
        if (data.error) {
            errorDiv.innerHTML = data.error;
        } else {
            resultDiv.innerHTML = data.message;
        }
    } catch (error) {
        errorDiv.innerHTML = 'Ошибка при отправке рассылки!';
    }
    Telegram.WebApp.MainButton.hide();
}