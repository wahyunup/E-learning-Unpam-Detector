import aiohttp
import asyncio
import os
from dotenv import load_dotenv
from bs4 import BeautifulSoup

load_dotenv()
sem = asyncio.Semaphore(10)

class unpamChecker():
    def __init__(self) -> None:
        self.username = os.getenv("UNPAM_NIM") or str(input("Masukan NIM kamu : "))
        self.password = os.getenv("UNPAM_PASS") or str(input("Masukan password E-learning kamu : "))
        self.URL = "https://e-learning.unpam.id/my/"
        self.LOGIN_URL = "https://e-learning.unpam.id/login/index.php"
        self.COURSE_API_URL = "https://e-learning.unpam.id/lib/ajax/service.php?"

    async def login(self, session):
        async with session.get(self.LOGIN_URL) as response:
            htmlSource = BeautifulSoup(await response.text(), "html.parser")
            loginToken = htmlSource.find_all("input", {"name":"logintoken"})[0].get('value')
            print(loginToken)
            dataLogin = {
                "anchor": "",
                "logintoken": loginToken,
                "username": self.username,
                "password": self.password
            }
            async with session.post(self.LOGIN_URL, data=dataLogin) as response:
                print(response.status)
                if response.status == 200:
                    return await response.text()
                else:
                    return False

    async def getCourseAPI(self, response, session):
        htmlSource = BeautifulSoup(response, "html.parser")
        dropDownMenu = htmlSource.find('div', id="carousel-item-main")
        logoutElement = dropDownMenu.find_all("a", class_="dropdown-item")
        sessionKey = logoutElement[-1].get("href").replace("https://e-learning.unpam.id/login/logout.php?sesskey=", "")
        params = [{"index":0,"methodname":"core_course_get_enrolled_courses_by_timeline_classification","args":{"offset":0,"limit":0,"classification":"all","sort":"fullname","customfieldname":"","customfieldvalue":""}}]
        async with session.post(self.COURSE_API_URL+"sesskey="+sessionKey+"&info=core_course_get_enrolled_courses_by_timeline_classification", json=params) as resp:
            data = await resp.json()
            return data[0]["data"]["courses"]

    async def getDiscussUrls(self, session, url):
        async with session.get(url) as response:
            htmlSource = BeautifulSoup(await response.text(), 'html.parser')
            forumDiscussList = htmlSource.find_all('li', class_='activity activity-wrapper forum modtype_forum hasinfo')
            forumDiscussUrls:list = []
            for item in forumDiscussList:
                discussUrl = item.find('a', class_="aalink stretched-link")
                if (discussUrl): forumDiscussUrls.append(discussUrl['href'])
                else: forumDiscussUrls.append(None)
            return forumDiscussUrls

    async def findDiscussExistence(self, session, url):
        async with sem:
            async with session.get(url) as response:
                htmlSource = BeautifulSoup(await response.text(), 'html.parser')
                discussTable = htmlSource.find('table', class_='table discussion-list generaltable')
                if discussTable != None:
                    discussForums = discussTable.find_all("tr", class_="discussion") #type: ignore
                    manyDiscussForum = len(discussForums)
                    for discussForum in discussForums:
                        if (len(discussForum['class']) == 2): manyDiscussForum -= 1
                    if manyDiscussForum >= 1: return True
                    else: return False

    async def getDiscussInfo(self, session, url):
        async with session.get(url) as response:
            htmlSource = BeautifulSoup(await response.text(), "html.parser")
            courseData = htmlSource.find_all('li', class_="breadcrumb-item")
            if courseData:
                courseTitle = courseData[0].a['title']
                forumTitle = courseData[1].span.text
                return [courseTitle, forumTitle, url]

    async def main(self):
        async with aiohttp.ClientSession(connector=aiohttp.TCPConnector(ssl=False)) as session:
            loginResp = await asyncio.create_task(self.login(session))
            if loginResp:
                print("[+] Getting course list...")
                courseDatas = await asyncio.create_task(self.getCourseAPI(loginResp, session))
                discussTasks:list = []
                courseName:list = []
                for courseData in courseDatas:
                    courseName.append(courseData["fullnamedisplay"])
                    discussTasks.append(asyncio.ensure_future(self.getDiscussUrls(session, courseData["viewurl"])))
                discussResults = await asyncio.gather(*discussTasks)
                discussDatas = dict(zip(courseName, discussResults))

                findDiscussTasks:list = []
                discussUrls:list = []
                for discussName in courseName:
                    for discussUrl in discussDatas[discussName]:
                        if discussUrl:
                            discussUrls.append(discussUrl)
                            findDiscussTasks.append(asyncio.create_task(self.findDiscussExistence(session, discussUrl)))
                print("[+] Getting Discuss Task...")
                forumResults = await asyncio.gather(*findDiscussTasks)
                forumDatas = dict(zip(discussUrls, forumResults))
                
                forumUrls:list = []
                getTitleTasks:list = []
                for url, status in forumDatas.items():
                    if (status and status != None): forumUrls.append(url)
                for forumUrl in forumUrls:
                    getTitleTasks.append(asyncio.create_task(self.getDiscussInfo(session, forumUrl)))
                print("[+] Getting Information About The Task...")
                titleResults = await asyncio.gather(*getTitleTasks)
                result:str = ""
                if len(getTitleTasks) != 0:
                    for i in range(len(titleResults)):
                        if (titleResults[i][0] != titleResults[i-1][0]):
                            result += titleResults[i][0] + "\n"
                            result += f'   {titleResults[i][1]} : {titleResults[i][2]}\n'
                        else:
                            if len(titleResults) == 1: result += titleResults[i][0] + "\n"
                            result += f'   {titleResults[i][1]} : {titleResults[i][2]}\n'
                    return result
                else: return "Selamat! kamu udah nyelesain semua tugas dosen, pasti dosen senang dan kamu aman"
            else: return "Gk bisa login, coba cek lagi deh"
            
if __name__ == "__main__":
    print(asyncio.run(unpamChecker().main()))