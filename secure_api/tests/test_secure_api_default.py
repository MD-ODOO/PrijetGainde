from odoo.tests import tagged
from odoo.addons.secure_api.tests.common import TestSecureApiCommon
from odoo.release import version_info  # (18, ...)

import logging

_logger = logging.getLogger(__name__)


@tagged("secure_api")
class TestSecureApiDefault(TestSecureApiCommon):
    def test_default_boolean(self):
        api = self.create_api(
            api_action="create",
            model_ids=["base.model_res_partner"],
            default_field_ids=[{"field_id": "active", "value": "False"}],
        )
        api_2 = self.create_api(
            api_action="create",
            model_ids=["base.model_res_partner"],
            default_field_ids=[{"field_id": "active", "value": "True"}],
        )
        # create new partner via API
        new_company = self.send_request("POST", api.route, json_data={"name": "New inactive company"})  # {...}
        company_record = self.assert_record_exists(record_data=new_company)
        self.assertFalse(company_record.active, f"API default field active=False does not work (company.active={company_record.active})")

        new_company_2 = self.send_request("POST", api_2.route, json_data={"name": "New company"})  # {...}
        company_record_2 = self.assert_record_exists(record_data=new_company_2)
        self.assertTrue(company_record_2.active, f"API default field active=True does not work (company.active={company_record_2.active})")
        pass

    def test_default_float_integer(self):
        value_int = 3
        value_float = 1234.7
        if version_info[0] >= 16:
            api = self.create_api(
                api_action="rest",
                model_ids=["base.model_res_partner"],
                default_field_ids=[
                    {"field_id": "color", "value": f"{value_int}"},  # int
                ],
            )
        else:
            api = self.create_api(
                api_action="rest",
                model_ids=["base.model_res_partner"],
                default_field_ids=[{"field_id": "color", "value": f"{value_int}"}, {"field_id": "credit_limit", "value": f"{value_float}"}],  # int  # float
            )
        new_req = self.send_request("POST", api.route, json_data={"name": "New partner"})
        new_record = self.assert_record_exists(record_data=new_req)
        if version_info[0] >= 16:
            self.assertEqual(new_record.color, value_int, f"API default field color ({new_record.color}) does not work (default={value_int})")
        else:
            self.assertEqual(new_record.color, value_int, f"API default field color ({new_record.color}) does not work (default={value_int})")
            self.assertEqual(new_record.credit_limit, value_float, f"API default field color ({new_record.credit_limit}) does not work (default={value_float})")
        pass

    def test_default_many2one_one2many_many2many(self):
        api = self.create_api(
            api_action="create",
            model_ids=["base.model_res_partner"],
            default_field_ids=[
                {"field_id": "country_id", "value": 'ref("base.vn")'},  # many2one
                {"field_id": "user_ids", "value": '[(0, 0, {"name": "test", "login": "test1"})]'},  # one2many
                {"field_id": "category_id", "value": '[(0, 0, {"name": "tag1"}), (0, 0, {"name": "tag2"})]'},
            ],
        )
        new_req = self.send_request("POST", api.route, json_data={"name": "New partner"})
        new_record = self.assert_record_exists(record_data=new_req)
        self.assertEqual(
            new_record.country_id.id, self.env.ref("base.vn").id, f'API default field country_id ({new_record.country_id.id}) does not work (default={self.env.ref("base.vn").id})'
        )
        self.assertEqual(new_record.user_ids.mapped("login"), ["test1"], f'API default field user_ids ({new_record.user_ids.mapped("login")}) does not work (default={["test1"]})')
        self.assertEqual(
            new_record.category_id.mapped("name"),
            ["tag1", "tag2"],
            f'API default field category_id ({new_record.category_id.mapped("name")}) does not work (default={["tag1", "tag2"]})',
        )
        pass

    def test_default_binary_char_selection(self):
        image_1920 = "/9j/4AAQSkZJRgABAgEASABIAAD/2wDFAAQFBQkGCQkJCQkKCAkICgsLCgoLCwwKCwoLCgwMDAwNDQwMDAwMDw4PDAwNDw8PDw0OERERDhEQEBETERMREQ0BBAYGCgkKCwoKCwsMDAwLDxASEhAPEhAREREQEh4iHBERHCIeF2oaExpqFxofDw8fGioRHxEqPC4uPA8PDw8PdAIEBAQIBggHCAgHCAYIBggICAcHCAgJBwcHBwcJCgkICAgICQoJCAgGCAgJCQkKCgkJCggJCAoKCgoKDhAODg53/8IAEQgA7ADsAwEiAAIRAQMRAv/EAIUAAAEEAwEAAAAAAAAAAAAAAAADBAUGAQIHCBAAAgICAgICAwEBAAAAAAAAAwQCBQEGADAREhMVBxAUIEARAAIBBQEBAAMAAAAAAAAAAAECAwAEERIgEBMFFHASAAMAAQMEAQQCAgMBAAAAAAABESEQMDEgQVFhcQISgZEiQGChUMHR8P/aAAgBAQAAAAD3wAZMAAAAAAAAbZNjTUNwA1wGdgADXO+TBlPGVAA10wKbAAAAzotlnFcGQAMBlKC1n1QACtchmbXdnIAAANObcua+lJsAAqfILdFSvTn4AAYiuTUohvTdiAAKxxW7xtYl+svWL/ORo6huLRc/tWfSU6AARPn+Z3iNZJpSrFKv4KCuaNSzNRr70XJgADPgcFb1qzWrBCMpKw8/mVIy34YVfsHbNwABDj1Zt8BBtHtOm1WusJOLKzkZSvQPVAAA059y15FSWkpS7dERF45fdGkdMwrf0DeAAAKrydhaHdRy3IhnaK/OuZ2HYSncXoAAYqFOQe+bOAdD7pItiS5n58tnf+rsp7pb0AANec1dxSvGvNOq+jOxwKlh8iea+i9U9PLv+mzgAANeGc7vufMnBJv0X6K2QV8d8h09Jejqjt2W6gAAx8t866i622cwElamNaxNwkpBwVX9OdWyAANOAxDqrt7vOwPPZuNiOozNdp0fPK9n6eAAGtDqERAQVis7/mPnF36etsDB0Re9Wrp9pAAArPnKr2q5byWq/A5zvNaxHUzm6He/QLkAABjyWoPrKtGsorhE125yOKnX8d/vuQAAGlEqrFtbN4XnvOU+kXzNJh7JaOwTWQAAIShJwLB3JvkY9jorF01rMXTr1j2AADWk0nTVg1jWE7YmNIi1JaE2nOjdNlwAAa8lrcLvLs69WnkqkxXUZqVOxdB69ctgACN49W6pMpbwsbCTCi+yFAtlbs/UOm9AXAAI/nFKpkY+Zspivw8de2FXira4sl7tvTpAAAi+O1eEiGsQyX0iYi9tqBA9ju8a8tfdZ4AAjPO1Y2dMK4gitvDy0qw59cukw6Ur6WsIABH+f+PKWPWvTazKrQUnZ5iPxY2MTfPQNhyAAy5dxLns9IVy0kRWmLx49nN3kLp2rrdqyH//2gAIAQIAAAAA2MGTBkMAGEcrYAyJbbARCcm4AG0S9kgIZoo+U2RTZpSkmBFRCy++7bXVrYnwDSG3zrjVXXE6sA0i08aZF8KyyoDGLS0jM6yqqk0sAziW4y32eYdzCgCcFqsqro0SczewCUQku5xqxay8pkBjE6bK7M0kHdjcAQ8Ea4yJi9ikgIaAbmobbOpuZAhq83yJCyi0rYM//9oACAEDAAAAANsBnAGcABhbTXAGcbGoE7iKQAHMuyjAJ96yj0cYWlJSChwJebh25k2fydWYgOZdoKaKpC8OkAs/1SeKJsldo3UBxIZSmhOEX0jtQHErnZ27ZsN0IvQDeWyljTfKyUVgDaVzppjddxHxgA5k1MabLZ3bQqQElJ5U33NtG0MyAlpJVwrjCWjaMiwJSb22ythJBOMiT//aAAgBAQABAgD/AD48f9Pr6+vjnr+/X19fX19c4/eMevr6+vr6+vr48fvz55nHjx/qXPH6xjsZNG2Vsxk6/HjhCHvF70ZOi1njIpJ3QTdjDFpsb5knqcvRb8Vn8Rs1d0sz1PO297OchGhr/TcQTzmZuMzprZKynaE2CNp9niynZRusWVhdWNsKYYOc8UkeizhiUHcnIONdCxZt37qv2KN5Cwf2NO5hbsGKEE4nsG6BOuH0NwswLkWBkFs7A0F30YAHFPllBNNqY7EYZplw4XQloR6D4uAqRgQrbURjagU66zQVSsoLG9fiXZxJyXpog+meLquKIbYZ5XArsQKep+JucYQH/JXVragU4Ta4ktqyHVe8yLIEalnhLCys6orLRyYIJrGQW0W8omUIpryCounPLeUV8rtWW87VO9qja+y0HxAGFtvsDXlabUtjIxmFTBafTLNo7izg1u2bpz7JXbvx8SSc0BJHU/IL/wBkhuenwrwEKo1Vk6Ws2DtlY05b5fZtae1+soNQIgckY8tGbpO61us1/R62MnHFX9bY6XubLxRZIv8AVjkKM9NNNdiGG8lbrUXaf6gkzWD0q/mlEx0txsq5aqmizkJ0Ws5eAzcD3Kw3FS0TWzxwhWp4ArKr0lbplizSJkrLIJKpjXjNbYKM51Ia3rJxEI3zOBlSIEVCv1Xo78Yl0QLpfzZ5Ehc7Yp+PF8kLiAmVbBZ5JQGnKBH1ODu674FxLcLEkZTbevbzUbZSwMULBCMAYCgjQVmOtqVjwqx+BcAQgThsR2dJVoV0sQkOwsl7FcdeuhjrsCH/AEaEhDIJ3LmQHqfqeYdbdMuKAZ1jKDkZdMuWLLDUWcyJLJDzw8vejuGrZ2zw/hqEswiyqaqsK9npZnYs4mdtV0kpydLMoSwbKznEAZHht0hG0GqwlKWOeh3jozYIb54lmxOZxZjGcS4x80zkyac8V0K6FZkOehrDQrPBlYmi4ZxZmcjZsLJO1UNYF+0jYqZKlXrp8WbSJ0PcdeYYOTAGIkmQi70yWY0hKSsOM4GWo4NUpa+xi7Sy6LDlwUTmSD47CUCLRT/mLCeVyYEzXMVNSNWbEPFfGj6Xo7FXkmOwVbbJ8o4xExJhw51WVmpGJAQ1+MSwzSAqs46G+Wwb9SWUCPEgT5PnYLLhohjAuGRExKDDLNXyiHWyx/j/2gAIAQIBAQIA8z7nPuc5zmmkV88ZouG4nKOknMkjSQHi6oMrib7fZpzOz7W3N4I/FoHY1g0athxOuuK22zWojiXiYklnoehKUpzPRpqYmf6LOr1HUfM4aiCv6364tQMRUnLiSlGqLhqPkKqOJC1ZVqxiRleEjmdy++4lMxn3aoZIm4uaJ2L77U1Bo6tubsmia232LJS1atxdgmiMNQGFUVbe/wD/2gAIAQMBAQIA8z7nPuc5zmo4WTnNKjJxYLNDJBzBBHbX0fH40tDcRtAYfiIVt7aJE/KNx+KkuZJJDQ8wKhlSS/fi1kknoAoEMZGfvM3EVZaldGVZZDItMH5hVA6i2htFhuLb4hXLcwFBQdLn7y3YbMyvyhjJbOSw8Srgk8IEJGGGAI0ZLhebdAmny+CwLAUVZklXizrXXRE0C6Ymq6HFj4tKNdWBo0wvObCkGCUOTTh2NXfv/9oACAEBAgM/Av8AHpov6KQmXchd2aU+0q2eTOkHS7f2jLpk/itnDM9E0R9IhCEfSIRS61n8dnBH0/bjWIuudL0/cRbOCdH28F0XR/IRBl6Ktya3SF6HzperG7EXTJ/E+4mv8TJdJr9x9q28dCQk+RfUidGNF9PcTETTJN5fQXg+ps+pcn3dP2Ib7n1nkT/oU/jpPqPvwYLr/EqZ9p2K97GuD71D0O8DXYaMa/xPvY12H4GmQzpVtY0ZFomfT4Pp8E6VT6X2PpXY+laUaZjawXqpD7XpT7n0Xoi3EIXRdGh/UfxTJ0opFt4GfV1IUwLuY6WfVR/3aybt0nSyj+gfQ2fcZ/qIT1SF/wALd2D/ALWNJ03YdMf0p1TqvTdu6zpx051g9MbOCb2SdP8AHZxp9v8AwWd3PX//2gAIAQIBAz8C/sP/2gAIAQMBAz8C/sP/2gAIAQECAz8h/wAehmeRi78O8cb2mGZIcN95SMjh7IvZwLrYG8bhJyVgbXSJvRnA+TE1aIJ3H7nnoQbueQicY+/QhJEiJs5FdKUZPSD8kqG9Ek0hUf7EFs1inBsqENg2yJrOmEKUIdhcEUiFwKr87WGLIuQpjoNNDY4NDcBpzQlpSJmdzFdMBWmBBy03T/TRBKi9bm76Zglk54cRgiTpLSG3rwEmdgP5Q6xoojG3VpkRWZ2Q0ysyXB3VzRcEjrgm4xw6R7kJol+yMyeCFEM+hHfogPAqw0YQyVbWXwZdZ4ZaEJZlHG4+hPEyULTP4GzFyMw4mRkqCGQrztmXwPMH5MGnOOwiC4IaKQuBskdoM4HDhnsaOGZwXaVvgohNIVdETRAk0mqrT9u2lkQ8huhcxKtKj3g40KhZO0ejQu5hlC99yuAslPYZUR6snSkdxFiJQi6UwXghkpXJNuosJpNYRMx+SlXRSEDnuRauwYmhaVDxOBGBSDTwMFyEkhhbmNMawWoT7CXbUXgbJoqhPchdKQpCaXSvgfgpghDJCdqJ6XRRdXpClEJEcpEOnBSLayLoyKY6TvRC6NGTjSIxs4fWyUySUqJkhXqk0hGzhj1XQyDKUQwNoY8C/oT01kyirs5aE+/TdGhQWlF4GqGxgyQrRhs5GNV0zrC9N1hSwi2cCYkQzphoxvoaGXRjyUY6v//aAAgBAgIDPyH/AAjG/j+1d5k/yH//2gAIAQMCAz8h/o0m9jSdV0nTVqtzO1npjLs17N38f0EkJ/4fjcnV/9oACAEBAgM/EP8Aj50XeX91MNyLkX5PJholqzvpa+x2+kJKtnH6G/z0KJEifndSVlWE+B8jrGy7mPjtlr4Bw9sUKqGSQJcNPboDZqipyxn5aP0bLbPRPzZiCfJzwY1J6z505zsbGEJqr40H7i62cAccsGJXl/grOT0KxfIRD6WzfjKPbPR4ljZpmZa9kVz+xtqUgssb4qPIc107o9FPY9bCYu8BvO2zB6E6ncYQorFkxVlTCFKL5FgkcxKUXamSZ0ORgRnwcKGg6Q7gEWz+rRxYZGsLsLN5FUlyVvBXIhPkTA7pVMIZLGhHCx3M4IF8IbZsS/N7VTXkpY0zE8DmNIvzHEJW1JnZCQrEWT9mfgZXTL0eTCMVu3kMN+wamnBzE+cFqV8iat8oqBiswQvxFTc+RSX+xFzzezhP2eGBIznQoLG3RCZEx3LWFfAIDZfklMfkylkFYqyUWuyKNc+TCYY3gGXZjJ5RRL7Ca2omQ/8A7uIeI0g2ZuWZq5CU08lpy2JaZYqerokdv+hunlkXnlBud5H+pZ2Gf3tRvsYEckaRTZ5hayXkPgxQfDM5JuwlRJvnRGRaeQptH4CqAynvwyhyY5EciWTFOBP2W+dr94eeZwuCXoR5eDiJlUO9zEgfwDErBoNTKsMxCEW3NehTFkXgCv8A6O5H/sur8jP7e1H7FPyKvklx8DVRYkeRJBjsWZEnCFjESTkhioyKhWSXomcH721U15KwVrSG7BLmX6Y7hES+CHwBF5nsKm6Sb7DFV5hhYJJ2aG0/yM4ZeUP/AGBWIMMmdttD8C+Bnli8nYRLAktES3BjFGKPLhxFdjuEQywuaOKos/aKR427mT2cTIkhdf4zFSg7FISIiia0LHkmXcteu5X2KPQrYReR3MSrRFRexwHERb58DMuTmTRCoi4mHE3wZOwmCfBumnkTbyVsmhMNjryZJfwL0vC4oL3FycDG5afkMSjFpLsi7WGNGNjAuhG4lFBJwTsNoZhsJ/NFCxZhO5gZNqrwhu6GzjGy4EtpDAgu+h9x3ahQJ8Um/J3BtBsYCrZ/QOhrk7/I2QaMFNIZ3BpLOjZ3ENGSuUaM0YeZP0fsLsrTwJHCOWVDHBLgTzEhA0z9niJb8iV6C4u5x9FIMMURezH+iuTDNHwNmPgMPNc6WxLHcYaUwREIvsJgmjaLsNDYHgfdFXnZ/WZfLPYE2IRnQ+xyCZCvgTSEWWFISmTIxgTFfudmB/KMHjZvxDr2UX0KSsvzKhCU4QjIkUTQhGRFN0uGb2YdnMTkcoj9BwNDfyDS1GXpEMwxZkaGRO4/ItciX5f9DWO2On//2gAIAQICAz8Q/opCewkXpjIXqg2Ppzo+m6Tqxs5OXTUTqumSdKa4Maxa42HCYHKNh6ZMbNZwG1JsYM7OOnD0hedZp5F1TVddXTz0Ppz1TYpNi9F0nT//2gAIAQMCAz8Q/ovjsm+BrldPMtwPreMdTD7046S1z+umR5ZC9E0goV/XS0E6Ui6IRclOqk6EKymDPTRIplECooZIRdahCaWXIiCpTBnpjRjWD6Ii9OTHUnyQcfVeufgpgj3ETTH56amXRfAhdP8At04/JjXPS7lWv//Z"
        city = "New York City"
        ftype = "delivery"
        api = self.create_api(
            api_action="rest",
            model_ids=["base.model_res_partner"],
            default_field_ids=[
                {"field_id": "image_1920", "value": image_1920},  # binary
                {"field_id": "city", "value": city},  # char
                {"field_id": "type", "value": ftype},  # selection
            ],
        )
        new_req = self.send_request("POST", api.route, json_data={"name": "New partner"})
        new_record = self.assert_record_exists(record_data=new_req)

        check = {
            "image_1920": image_1920,
            "city": city,
            "type": ftype,
        }
        for fname, ftest_val in check.items():
            if fname == "image_1920":
                ftest_val = ftest_val.encode("utf-8")  # byte
            self.assertEqual(getattr(new_record, fname), ftest_val, f"API default field {fname} ({getattr(new_record, fname)}) does not work (default={ftest_val})")
