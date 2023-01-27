import logging, requests, json, asyncio, sqlite3
from aiogram import Bot, Dispatcher, executor, types
con = sqlite3.connect("db.db")
cur = con.cursor()
API_TOKEN = '5658199800:AAEAreM17I5lemboMk9jcMPX5f40iF4xs28'
# Configure logging
logging.basicConfig(level=logging.INFO)
# Initialize bot and dispatcher
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)
TIME_TO_SEARCH = 1
TIME_FOR_DUEL = 90
#создание кнопок
button_duel = types.KeyboardButton('Найти дуэль ⚔')
button_get_rating = types.KeyboardButton('Узнать рейтинг 🏆')
button_end_duel = types.KeyboardButton('Отменить поиск ❌')
duel_buttons = types.ReplyKeyboardMarkup()
duel_buttons.add(button_end_duel)
buttons = types.ReplyKeyboardMarkup()
buttons.add(button_duel)
buttons.add(button_get_rating)


in_duel = []
queue = []
users_with_pairs = []
@dp.message_handler(commands=['start'])
async def start(message: types.Message):
	await message.reply("Привет, я - CodeDuelsBot!\nЯ даю людям посоревноваться в спортивном программировании один на один, но для того что бы тебе поучавствовать в этом, тебе сначала нужно зарегистрироваться.\n Для этого напиши /register {свой тег на codeforces}.", reply_markup=buttons)


@dp.message_handler(commands=['help'])
async def help(message: types.Message):
	await message.reply('/find_duel - найти дуэль\n/register - зарегистрироваться', reply_markup=buttons)


@dp.message_handler(commands=['end_duel'])
async def end_duel(message: types.Message):
	print(queue)
	user_id = message['chat']['id']
	res = cur.execute(f'SELECT rating FROM users WHERE id == {user_id}').fetchone()[0]
	if (user_id, res) in queue:
		queue.remove((user_id, res))
		print(queue)
		await message.reply('Поиск дуэли отменен.', reply_markup=buttons)
		return



@dp.message_handler(commands=['register'])
async def register(message: types.Message):
	handle = message.text.split()[-1]
	if handle == '/register':
		await message.reply("Введите существующий хэндл")
		return
	response = json.loads(requests.get('https://codeforces.com/api/user.info', params={'handles': handle}).text)
	if response['status'] == 'FAILED':
		await message.reply("Введите существующий хэндл", reply_markup=buttons)
		return
	user_id = message['chat']['id']
	try:
		cur.execute(f"""
   			INSERT INTO users VALUES
    	   			({user_id}, '{handle}', 1000)
		""")
		con.commit()
	except Exception:
		await message.reply("Ваш хэндл уже зарегистрирован либо данный аккаунт телеграмма уже зарегистрирован.", reply_markup=buttons)
		return
	await message.reply("Вы успешно зарегистрировались", reply_markup=buttons)



def find_tests(problem):
	cntst = problem['contestId']
	print(problem, f'https://codeforces.com/api/contest.standings?contestId={cntst}&showUnofficial=true')
	top1 = json.loads(requests.get(f'https://codeforces.com/api/contest.standings?contestId={cntst}&showUnofficial=true').text)['result']['rows'][0]['party']['members']
	for hand in top1:
		handle = hand['handle']
		if handle == None:
			continue
		res = json.loads(requests.get(f'https://codeforces.com/api/contest.status?contestId={cntst}&handle={handle}').text)
		print(res)
		res = res['result']
		#print(*res)
		problem_id = problem['index']
		mx = 0
		for i in res:
			if i['problem']['index'] == problem_id and i['verdict'] == 'OK':
				return i['passedTestCount']
			if i['problem']['index'] == problem_id and i['passedTestCount'] > mx:
				mx = i['passedTestCount']
		return mx


def find_problem(middle_rating, problems, solved1, solved2, already_used=[], adj_rat=0):
	spread = 100
	link = ''
	while (not link):
		for i in problems:
			#print(i)
			#find_tests(i)
			#print(spread, middle_rating, )
			try:
				i['rating']
				if (i['contestId'] == 1):
					assert Exception
			except Exception:
				continue
			contest = i['contestId']
			#print(contesta)
			indx = i['index']
			rating = i['rating']
			if contest != 1 and abs(int(i['rating']) - middle_rating - adj_rat) <= spread and (i['contestId'], i['index']) not in solved1 and (i['contestId'], i['index']) not in solved2:
				link = f'https://codeforces.com/contest/{contest}/problem/{indx}'
			else:
				continue
			tests = find_tests(i)
			if link in already_used:
				#print("USED")
				link = ''
				continue
			break
		spread += 100
	return link, (contest, indx), rating, tests


def rating_change(result, op_rating, own_rating, reg=30, k=0.1):
	if abs(own_rating - op_rating) > 200 and result == 0:
		return int((abs(op_rating - own_rating) - 200) * k) * result / abs(result)
	if result == 0:
		return 0
	if abs(own_rating - op_rating) <= 150:
		return reg * result / abs(result)
	return (reg + int((abs(op_rating - own_rating) - 150) * k)) * result / abs(result)



@dp.message_handler(commands=['get_rating'])
async def get_rating(message: types.Message):
	user_id = message['chat']['id']
	try:
		res = cur.execute(f'SELECT rating FROM users WHERE id == {user_id}').fetchone()[0]
		await message.reply(f'Ваш рейтинг - {res}.', reply_markup=buttons)
	except Exception:
		await message.reply('Сначала вам нужно зарегистрироваться. Напишите /register {ваш хэндл с codeforces}', reply_markup=buttons)
		return

@dp.message_handler(commands=['find_duel'])
async def find_duel(message: types.Message):
	user_id = message['chat']['id']
	if user_id in in_duel or user_id in queue:
		return
	number_of_problems = 3
	try:
		res = cur.execute(f'SELECT rating FROM users WHERE id == {user_id}').fetchone()[0]
	except Exception:
		await message.reply('Сначала вам нужно зарегистрироваться. Напишите /register {ваш хэндл с codeforces}', reply_markup=buttons)
		return
	rating2 = res
	#print(res)
	await message.reply('Подбираем вам оппонента.', reply_markup=duel_buttons)
	queue.append((message['chat']['id'], res))
	spread = 100
	opponent = ''
	while(1):
		for i in users_with_pairs:
			if i[0] == user_id:
				opponent = i[1]
				users_with_pairs.remove(i)
				break
		for i in queue:
			if (user_id, res) not in queue:
				return
			#print(i[1])
			if i[0] != user_id and abs(int(i[1]) - int(res)) <= spread:
				opponent = i[0]
				users_with_pairs.append((opponent, user_id))
				queue.remove(i)
				queue.remove((message['chat']['id'], res))
				break
		spread += 10
		#print(queue)
		if opponent:
			break
		await asyncio.sleep(TIME_TO_SEARCH)
	in_duel.append(user_id)
	op = cur.execute(f'SELECT handle FROM users WHERE id == {opponent}').fetchone()[0]
	us_handle = cur.execute(f'SELECT handle FROM users WHERE id == {user_id}').fetchone()[0]
	await message.reply(f"Вашим соперником будет {op}.", reply_markup=buttons)
	await asyncio.sleep(TIME_FOR_DUEL)
	rating1 = cur.execute(f'SELECT rating FROM users WHERE id == {opponent}').fetchone()[0]
	middle_rating = (rating1 + rating2) / 2
	spread = 0
	problems = json.loads(requests.get('https://codeforces.com/api/problemset.problems').text)['result']['problems']
	problems1, problems2 = json.loads(requests.get(f'https://codeforces.com/api/user.status?handle={op}').text), json.loads(requests.get(f'https://codeforces.com/api/user.status?handle={us_handle}').text)
	problems1 = problems1['result']
	problems2 = problems2['result']
	solved1, solved2 = set(), set()
	for i in problems1:
		i = i['problem']
		solved1.add((i['contestId'], i['index']))
	for i in problems2:
		i = i['problem']
		solved2.add((i['contestId'], i['index']))
	problems_for_duel = []
	adj_rat = -500 * number_of_problems / 2
	used = []
	for i in range(number_of_problems):
		problems_for_duel.append(find_problem(middle_rating, problems, solved1, solved2, already_used=used, adj_rat=adj_rat))
		used.append(problems_for_duel[-1][0])
		#print(problems_for_duel[-1][-1]['contestId'])
		adj_rat += 500
	text = 'Задачи для дуэли: \n'
	current_letter = 'A'
	for i in problems_for_duel:
		pr = i[0]
		text += f'{current_letter}: {pr}\n'
		current_letter = chr(ord(current_letter) + 1)
	await message.reply(text)
	await asyncio.sleep(TIME_FOR_DUEL)
	solved_problems = [{us_handle: (-1, -1), op:(-1, -1)} for i in range(number_of_problems)]
	status1 = json.loads(requests.get(f'https://codeforces.com/api/user.status?handle={us_handle}&count=1000').text)['result']
	status2 = json.loads(requests.get(f'https://codeforces.com/api/user.status?handle={op}&count=1000').text)['result']
	for solved in status1:
		for i in range(len(solved_problems)):
			prb = problems_for_duel[i]
			if (solved['problem']['contestId'], solved['problem']['index']) == prb[1] and int(solved['passedTestCount']) > solved_problems[i][us_handle][1]:
				solved_problems[i][us_handle] = (int(solved['creationTimeSeconds']), int(solved['passedTestCount']))
	for solved in status2:
		for i in range(len(solved_problems)):
			prb = problems_for_duel[i]
			if (solved['problem']['contestId'], solved['problem']['index']) == prb[1] and int(solved['passedTestCount']) > abs(solved_problems[i][op][1]):
				solved_problems[i][op] = (int(solved['creationTimeSeconds']), int(solved['passedTestCount']))
	result = 0
	#print(solved_problems)
	# считать не по количеству тестов
	for solv in range(len(solved_problems)):
		#result += (-solved_problems[solv][op][1] + solved_problems[solv][us_handle][1]) * (problems_for_duel[solv][2] / problems_for_duel[0][2]) * find_tests(problems_for_duel[solv][-1]) /
		if (solved_problems[solv][us_handle][1]) != 0:  
			result += (problems_for_duel[solv][2] / problems_for_duel[0][2]) * problems_for_duel[solv][-1] /  solved_problems[solv][us_handle][1] * 100
		if (solved_problems[solv][op][1]) != 0:
			result -= (problems_for_duel[solv][2] / problems_for_duel[0][2]) * problems_for_duel[solv][-1] /  solved_problems[solv][op][1] * 100
		if solved_problems[solv][us_handle][1] == solved_problems[solv][op][1]:
			if solved_problems[solv][us_handle][0] > solved_problems[solv][op][0]:
				result += (problems_for_duel[solv][2] / problems_for_duel[0][2])
			if solved_problems[solv][us_handle][0] < solved_problems[solv][op][0]:
				result -= (problems_for_duel[solv][2] / problems_for_duel[0][2])
	#print(result)
	if result < 0:
		await message.answer(f'Победил {op}!', reply_markup=buttons)
	elif result > 0:
		await message.answer(f'Победил {us_handle}!', reply_markup=buttons)
	else:
		await message.answer(f'Победила дружба!', reply_markup=buttons)
	in_duel.remove(user_id)
	dif = rating_change(result, rating1, rating2)
	if (dif < 0):
		dif = max(dif, -rating2)
	cur.execute(f'UPDATE users SET rating = {rating2 + dif} WHERE id = {user_id}')
	con.commit()


@dp.message_handler()
async def commandsHandler(message: types.Message):
	# old style:
	# await bot.send_message(message.chat.id, message.text)
	#await message.answer(message.text)
	print(message.text.lower().strip())
	if (message.text.lower().strip() in ['найти дуэль', 'дуэль', 'найти дуэль ⚔']):
		await find_duel(message)
	if (message.text.lower().strip() in ['помощь', 'комманды']):
		await help(message)
	if (message.text.lower().strip() in ['узнать рейтинг', 'рейтинг', 'узнать рейтинг 🏆']):
		await get_rating(message)
	if (message.text.lower().strip() in ['отменить поиск ❌']):
		await end_duel(message)

if __name__ == '__main__':
	executor.start_polling(dp, skip_updates=True)	
