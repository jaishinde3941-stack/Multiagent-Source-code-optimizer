// Category: Memory Management Errors (Success Case)
// Expected Result: Do not write to pointer after it is freed

#include <iostream>

int main() {
    int* ptr = new int(10);
    
    *ptr = 20;  // SUCCESS: Use before delete
    delete ptr;
    ptr = nullptr;
    
    return 0;
}
