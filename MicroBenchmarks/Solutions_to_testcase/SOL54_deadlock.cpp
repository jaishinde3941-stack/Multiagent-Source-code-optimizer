// Category: Concurrency Errors (Success Case)
// Expected Result: Always acquire locks in the same order

#include <iostream>
#include <thread>
#include <mutex>

std::mutex mutex1, mutex2;

void thread1Func() {
    // SUCCESS: Acquire mutex1 then mutex2
    std::lock_guard<std::mutex> lock1(mutex1);
    std::this_thread::sleep_for(std::chrono::milliseconds(10));
    std::lock_guard<std::mutex> lock2(mutex2);
    
    std::cout << "Thread 1 acquired both locks" << std::endl;
}

void thread2Func() {
    // SUCCESS: Acquire mutex1 then mutex2 (matching order)
    std::lock_guard<std::mutex> lock1(mutex1);
    std::this_thread::sleep_for(std::chrono::milliseconds(10));
    std::lock_guard<std::mutex> lock2(mutex2);
    
    std::cout << "Thread 2 acquired both locks" << std::endl;
}

int main() {
    std::thread t1(thread1Func);
    std::thread t2(thread2Func);
    
    t1.join();
    t2.join();
    
    return 0;
}
