"""RCON replies stay framed across fragmentation and response continuation."""
import select
import socket
import struct
import threading
import time
import unittest
from test_live import RconClient


class RconFraming(unittest.TestCase):
    def test_delimited_large_reply_does_not_lose_partial_packets(self):
        local,remote=socket.socketpair();errors=[]
        local.settimeout(3);remote.settimeout(3)
        def exact(size):
            result=b''
            while len(result)<size:
                part=remote.recv(size-len(result))
                if not part:raise EOFError('Request disappeared')
                result+=part
            return result
        def receive():
            size=struct.unpack('<i',exact(4))[0];data=exact(size)
            return struct.unpack('<ii',data[:8])[0],data[8:-2].decode()
        def frame(number,text):
            body=struct.pack('<ii',number,0)+text.encode()+b'\0\0'
            return struct.pack('<i',len(body))+body
        def server():
            try:
                for text in ['large','next']:
                    number,command=receive();self.assertEqual(command,text)
                    self.assertFalse(select.select([remote],[],[],.02)[0], 'Client pipelined another request')
                    remote.sendall(frame(number,'first:'))
                    end,command=receive();self.assertEqual(command,'list')
                    tail=frame(number,'x'*5000+':last')
                    remote.sendall(tail[:7]);time.sleep(.2);remote.sendall(tail[7:])
                    remote.sendall(frame(end,'terminator'))
            except BaseException as error:errors.append(error)
            finally:remote.close()
        thread=threading.Thread(target=server);thread.start()
        client=RconClient.__new__(RconClient);client.sock=local;client.req_id=0
        try:
            for text in ['large','next']:self.assertEqual(client.cmd(text),'first:'+'x'*5000+':last')
        finally:client.close();thread.join(timeout=5)
        self.assertFalse(thread.is_alive());self.assertEqual(errors,[])


if __name__=='__main__':unittest.main()
