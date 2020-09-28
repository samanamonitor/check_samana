SRC_CEPH=check_ceph_df2 \
	check_ceph_mon2 \
	check_ceph_osd2

SRC_SAMANA2=check_samana2.py \
	check_winrm.py 

SRC_CTX_FARM=check_ctx_farm.py \
	check_ctx_apps.py

install: $(SRC_SAMANA2) $(SRC_CTX_FARM)
	install $^ /usr/local/nagios/libexec