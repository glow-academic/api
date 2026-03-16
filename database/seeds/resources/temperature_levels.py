"""Temperature level resource seeds.

122 rows defining discrete temperature values for AI model inference,
ranging from 0.0 to 1.2.
"""

from uuid import UUID

temperature_levels = [
    dict(id=UUID("019c441a-0e9e-7bef-841d-5d33999c9d12"), temperature=0.0),
    dict(
        id=UUID("019c441a-0e9e-7c74-928c-7c0739193aff"), temperature=0.3799999952316284
    ),
    dict(
        id=UUID("019c441a-0e9e-7c8c-bd56-1fa93aa79c09"), temperature=1.0700000524520874
    ),
    dict(
        id=UUID("019c441a-0e9e-7c9e-8acc-69725eead5b3"), temperature=0.07000000029802322
    ),
    dict(
        id=UUID("019c441a-0e9e-7ca4-ad96-a64b4ddb14b4"), temperature=0.5299999713897705
    ),
    dict(
        id=UUID("019c441a-0e9e-7cc4-83a2-f576e1eac21e"), temperature=0.7099999785423279
    ),
    dict(
        id=UUID("019c441a-0e9e-7cd3-9f45-b7f2ddd50383"), temperature=0.6100000143051147
    ),
    dict(
        id=UUID("019c441a-0e9e-7cdc-b2f0-1daefbf9a0d2"), temperature=0.5099999904632568
    ),
    dict(
        id=UUID("019c441a-0e9e-7ce6-a3df-5d1581d924f8"), temperature=0.07999999821186066
    ),
    dict(
        id=UUID("019c441a-0e9e-7cf7-b9c2-b296333b30ee"), temperature=0.28999999165534973
    ),
    dict(
        id=UUID("019c441a-0e9e-7d01-bde4-ccddced38deb"), temperature=1.1299999952316284
    ),
    dict(
        id=UUID("019c441a-0e9e-7d1a-9b3d-4b030af5a5f5"),
        temperature=0.009999999776482582,
    ),
    dict(
        id=UUID("019c441a-0e9e-7d22-aa42-b094ce03c315"), temperature=0.8700000047683716
    ),
    dict(
        id=UUID("019c441a-0e9e-7d2d-a122-d5e27a709e64"), temperature=0.47999998927116394
    ),
    dict(
        id=UUID("019c441a-0e9e-7d34-beaf-cb977faaad88"), temperature=0.49000000953674316
    ),
    dict(
        id=UUID("019c441a-0e9e-7d45-9f98-9437d0e6ab88"), temperature=1.1699999570846558
    ),
    dict(
        id=UUID("019c441a-0e9e-7d59-bd04-7501bbcf1b85"),
        temperature=0.029999999329447746,
    ),
    dict(
        id=UUID("019c441a-0e9e-7d64-8576-ebd89095d7ea"), temperature=1.1100000143051147
    ),
    dict(
        id=UUID("019c441a-0e9e-7d6f-a261-373c6e370d11"), temperature=1.059999942779541
    ),
    dict(
        id=UUID("019c441a-0e9e-7d7b-bc87-9f7dea25da62"), temperature=1.0099999904632568
    ),
    dict(
        id=UUID("019c441a-0e9e-7d84-b9a5-aa946d36a18d"), temperature=0.7400000095367432
    ),
    dict(
        id=UUID("019c441a-0e9e-7d9e-b960-c7edff5d9bce"), temperature=0.5799999833106995
    ),
    dict(
        id=UUID("019c441a-0e9e-7da6-ae62-6e2a16407f9d"), temperature=0.4300000071525574
    ),
    dict(
        id=UUID("019c441a-0e9e-7db9-b0f3-8d485af3cc59"), temperature=0.7599999904632568
    ),
    dict(
        id=UUID("019c441a-0e9e-7dcd-be35-3ab6d31cfb17"), temperature=0.41999998688697815
    ),
    dict(
        id=UUID("019c441a-0e9e-7dd6-b25d-1fa87885be16"), temperature=0.4699999988079071
    ),
    dict(
        id=UUID("019c441a-0e9e-7dde-a7b4-fa61b030af17"), temperature=0.5699999928474426
    ),
    dict(
        id=UUID("019c441a-0e9e-7de7-b3eb-b3831cbaaacd"), temperature=1.100000023841858
    ),
    dict(
        id=UUID("019c441a-0e9e-7dfb-9078-f1a2807595ff"), temperature=0.8600000143051147
    ),
    dict(
        id=UUID("019c441a-0e9e-7e0e-93ba-b9080f53300b"), temperature=0.05999999865889549
    ),
    dict(
        id=UUID("019c441a-0e9e-7e19-89e1-76a54e0e513b"),
        temperature=0.019999999552965164,
    ),
    dict(
        id=UUID("019c441a-0e9e-7e2b-91ce-0aadfc9baef7"), temperature=0.7699999809265137
    ),
    dict(
        id=UUID("019c441a-0e9e-7e37-a9f8-4388d8363acc"), temperature=0.6600000262260437
    ),
    dict(
        id=UUID("019c441a-0e9e-7e3d-b9e4-8df4302ca526"), temperature=0.7200000286102295
    ),
    dict(
        id=UUID("019c441a-0e9e-7e45-879f-3d0273bf2d3f"), temperature=1.1799999475479126
    ),
    dict(
        id=UUID("019c441a-0e9e-7e52-b580-9218337e5382"), temperature=0.7799999713897705
    ),
    dict(
        id=UUID("019c441a-0e9e-7e5a-933e-d1c96ab450fe"), temperature=0.949999988079071
    ),
    dict(id=UUID("019c441a-0e9e-7e62-b187-072e351576b7"), temperature=0.25),
    dict(
        id=UUID("019c441a-0e9e-7e69-a60a-627a1928dda8"), temperature=0.09000000357627869
    ),
    dict(
        id=UUID("019c441a-0e9e-7e73-ab7c-6b05701f3683"), temperature=0.6299999952316284
    ),
    dict(
        id=UUID("019c441a-0e9e-7e89-8b78-5a89a8ee38df"), temperature=0.800000011920929
    ),
    dict(
        id=UUID("019c441a-0e9e-7e94-9c38-b7f44e86a101"), temperature=0.8299999833106995
    ),
    dict(
        id=UUID("019c441a-0e9e-7ea0-afe1-143d03e99a25"), temperature=0.20000000298023224
    ),
    dict(
        id=UUID("019c441a-0e9e-7eb0-ba12-fa36a878cdef"), temperature=0.9800000190734863
    ),
    dict(id=UUID("019c441a-0e9e-7ebf-83f0-e822b230d010"), temperature=0.75),
    dict(
        id=UUID("019c441a-0e9e-7ec9-8819-23cf95608dbe"), temperature=0.6700000166893005
    ),
    dict(
        id=UUID("019c441a-0e9e-7ed1-9766-04be0f1c6b20"), temperature=0.10000000149011612
    ),
    dict(
        id=UUID("019c441a-0e9e-7ede-ab08-a9ec02a3d29f"), temperature=0.33000001311302185
    ),
    dict(
        id=UUID("019c441a-0e9e-7ef6-8811-b13973658720"), temperature=0.9100000262260437
    ),
    dict(
        id=UUID("019c441a-0e9e-7f01-84e3-fa33af4cc4e7"), temperature=1.2000000476837158
    ),
    dict(
        id=UUID("019c441a-0e9e-7f0d-9e4b-4b564ec66598"), temperature=0.14000000059604645
    ),
    dict(
        id=UUID("019c441a-0e9e-7f17-8e56-51c37a3b1098"), temperature=1.0199999809265137
    ),
    dict(
        id=UUID("019c441a-0e9e-7f26-8ca6-a1b33fb97fbe"), temperature=0.3499999940395355
    ),
    dict(
        id=UUID("019c441a-0e9e-7f2e-81d2-2545ba70f21d"), temperature=0.7300000190734863
    ),
    dict(
        id=UUID("019c441a-0e9e-7f39-855d-5f2802eeae74"), temperature=1.090000033378601
    ),
    dict(
        id=UUID("019c441a-0e9e-7f44-bb0b-5190a35cc0c0"), temperature=0.9300000071525574
    ),
    dict(
        id=UUID("019c441a-0e9e-7f53-8a08-d51406e55622"), temperature=0.20999999344348907
    ),
    dict(
        id=UUID("019c441a-0e9e-7f5f-9e3d-9922fdb0fdff"), temperature=0.8100000023841858
    ),
    dict(
        id=UUID("019c441a-0e9e-7f6c-a798-8328630ab038"), temperature=0.9900000095367432
    ),
    dict(
        id=UUID("019c441a-0e9e-7f74-9bcc-4512edb5fdcd"), temperature=1.0299999713897705
    ),
    dict(
        id=UUID("019c441a-0e9e-7f80-a9cb-7b1c947ad4c8"), temperature=0.8199999928474426
    ),
    dict(
        id=UUID("019c441a-0e9e-7f8f-b0cf-ab7d52866f69"), temperature=0.05000000074505806
    ),
    dict(
        id=UUID("019c441a-0e9e-7f94-a17b-863790cfbf00"), temperature=1.1200000047683716
    ),
    dict(
        id=UUID("019c441a-0e9e-7fa5-87e8-3e52d48647cd"), temperature=0.7900000214576721
    ),
    dict(
        id=UUID("019c441a-0e9e-7fae-bed9-1177ce0bd598"), temperature=0.8899999856948853
    ),
    dict(
        id=UUID("019c441a-0e9e-7fbb-84b9-a7962089afa4"), temperature=0.3199999928474426
    ),
    dict(
        id=UUID("019c441a-0e9e-7fc1-8cef-8914d6b01390"), temperature=0.30000001192092896
    ),
    dict(
        id=UUID("019c441a-0e9e-7fcd-afc7-37cf75ba25a7"), temperature=0.5400000214576721
    ),
    dict(
        id=UUID("019c441a-0e9e-7fde-a372-d6c53b939a2d"), temperature=0.8399999737739563
    ),
    dict(
        id=UUID("019c441a-0e9e-7fee-be99-7292d6d5e130"), temperature=0.44999998807907104
    ),
    dict(
        id=UUID("019c441a-0e9e-7ff9-8627-a980b71f8514"), temperature=0.2800000011920929
    ),
    dict(
        id=UUID("019c441a-0e9f-7004-9320-7d40cf5cd428"), temperature=0.5600000023841858
    ),
    dict(id=UUID("019c441a-0e9f-700c-a8c5-11434dc2ea95"), temperature=1.0),
    dict(
        id=UUID("019c441a-0e9f-7016-9973-59eca073bebe"), temperature=0.6399999856948853
    ),
    dict(
        id=UUID("019c441a-0e9f-7027-b2b3-40f7679aa440"), temperature=0.10999999940395355
    ),
    dict(
        id=UUID("019c441a-0e9f-7030-a571-3dddb574f57e"), temperature=1.0399999618530273
    ),
    dict(
        id=UUID("019c441a-0e9f-7038-a8fe-a960af92c6cd"), temperature=0.699999988079071
    ),
    dict(
        id=UUID("019c441a-0e9f-7055-8c67-a6f96ebb872b"), temperature=0.36000001430511475
    ),
    dict(
        id=UUID("019c441a-0e9f-7067-a9d9-66f6b22a620c"), temperature=0.03999999910593033
    ),
    dict(
        id=UUID("019c441a-0e9f-7076-b0f4-d3db8a59a2bf"), temperature=0.6899999976158142
    ),
    dict(
        id=UUID("019c441a-0e9f-7087-a7c2-481e3cf67900"), temperature=0.5199999809265137
    ),
    dict(
        id=UUID("019c441a-0e9f-708c-ace6-6ab6bfb9032b"), temperature=0.12999999523162842
    ),
    dict(
        id=UUID("019c441a-0e9f-70a7-8312-c8913b2bd033"), temperature=0.8799999952316284
    ),
    dict(
        id=UUID("019c441a-0e9f-70b3-bad8-286a24dc5f49"), temperature=0.3400000035762787
    ),
    dict(
        id=UUID("019c441a-0e9f-70be-928f-7873d52a9642"), temperature=0.15000000596046448
    ),
    dict(
        id=UUID("019c441a-0e9f-70ce-849a-af4b11bbfaf6"), temperature=0.9700000286102295
    ),
    dict(
        id=UUID("019c441a-0e9f-70d9-8046-2d636f526116"), temperature=0.6800000071525574
    ),
    dict(
        id=UUID("019c441a-0e9f-70e8-8235-7196b41406e1"), temperature=0.2199999988079071
    ),
    dict(
        id=UUID("019c441a-0e9f-70f0-a568-30584bfef8fb"), temperature=0.9599999785423279
    ),
    dict(
        id=UUID("019c441a-0e9f-7101-afd8-b2e50bc968f9"), temperature=0.8999999761581421
    ),
    dict(
        id=UUID("019c441a-0e9f-710b-99b2-3db575f01df1"), temperature=0.9399999976158142
    ),
    dict(
        id=UUID("019c441a-0e9f-7116-ab87-05d7035642c7"), temperature=0.38999998569488525
    ),
    dict(
        id=UUID("019c441a-0e9f-7120-bc1c-1e290802109a"), temperature=0.5899999737739563
    ),
    dict(
        id=UUID("019c441a-0e9f-712f-ad29-33e6889ca042"), temperature=0.4399999976158142
    ),
    dict(
        id=UUID("019c441a-0e9f-713c-87f4-1ce375f0e09f"), temperature=0.6200000047683716
    ),
    dict(
        id=UUID("019c441a-0e9f-715a-8037-ac5450f006cb"), temperature=0.6000000238418579
    ),
    dict(
        id=UUID("019c441a-0e9f-7166-a4b2-8eef873a73e7"), temperature=0.3700000047683716
    ),
    dict(
        id=UUID("019c441a-0e9f-716f-9341-e1c1d078369b"), temperature=0.1599999964237213
    ),
    dict(
        id=UUID("019c441a-0e9f-7176-a9ff-74d14b50e469"), temperature=0.18000000715255737
    ),
    dict(
        id=UUID("019c441a-0e9f-717c-a206-7bd132c85277"), temperature=1.149999976158142
    ),
    dict(id=UUID("019c441a-0e9f-718b-9bf3-c0143fa5d3c1"), temperature=0.5),
    dict(
        id=UUID("019c441a-0e9f-7318-8ee1-f4d7e0e89e26"), temperature=1.0800000429153442
    ),
    dict(
        id=UUID("019c441a-0e9f-732f-ac4d-b10174e69e21"), temperature=0.1899999976158142
    ),
    dict(
        id=UUID("019c441a-0e9f-7335-a559-31fe7e8db595"), temperature=0.4099999964237213
    ),
    dict(
        id=UUID("019c441a-0e9f-7342-b632-93b9c0f5ffe5"), temperature=1.1399999856948853
    ),
    dict(
        id=UUID("019c441a-0e9f-735a-81cf-eed6e8196398"), temperature=0.11999999731779099
    ),
    dict(
        id=UUID("019c441a-0e9f-7370-856d-7b31ced06c90"), temperature=0.23000000417232513
    ),
    dict(
        id=UUID("019c441a-0e9f-737e-9ffd-4759a8a321aa"), temperature=1.159999966621399
    ),
    dict(
        id=UUID("019c441a-0e9f-738a-9c75-c3dc21a1aed4"), temperature=0.46000000834465027
    ),
    dict(
        id=UUID("019c441a-0e9f-7392-981f-328740c079b2"), temperature=1.0499999523162842
    ),
    dict(
        id=UUID("019c441a-0e9f-73a7-8628-636b0586d4fb"), temperature=0.23999999463558197
    ),
    dict(
        id=UUID("019c441a-0e9f-73b3-b4c6-96f71113e8dc"), temperature=0.550000011920929
    ),
    dict(
        id=UUID("019c441a-0e9f-73b7-a591-e6cb67cc219a"), temperature=0.27000001072883606
    ),
    dict(
        id=UUID("019c441a-0e9f-73c1-94fd-f1e4fe4df3be"), temperature=1.190000057220459
    ),
    dict(
        id=UUID("019c441a-0e9f-73ca-8872-97569ea04c56"), temperature=0.6499999761581421
    ),
    dict(
        id=UUID("019c441a-0e9f-73d9-a939-23bb7a0cc094"), temperature=0.4000000059604645
    ),
    dict(
        id=UUID("019c441a-0e9f-73e9-9074-5fc628f2e51c"), temperature=0.17000000178813934
    ),
    dict(
        id=UUID("019c441a-0e9f-73f9-b1ae-e42dda0fd3c5"), temperature=0.25999999046325684
    ),
    dict(
        id=UUID("019c441a-0e9f-7413-be9e-8c771dd1ceb2"), temperature=0.9200000166893005
    ),
    dict(
        id=UUID("019c441a-0e9f-741c-889d-c67c16f9dc2b"), temperature=0.3100000023841858
    ),
    dict(
        id=UUID("019c441a-0e9f-742a-995a-2c0c8e1cffba"), temperature=0.8500000238418579
    ),
]
